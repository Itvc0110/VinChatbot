from __future__ import annotations

import argparse
import json
import logging
import sys

from vinchatbot.app.core.config import get_settings
from vinchatbot.app.ingest.chunker import chunk_document
from vinchatbot.app.ingest.crawler import read_raw_documents, write_structured_records
from vinchatbot.app.ingest.indexer import index_chunks

logger = logging.getLogger(__name__)

# Low-value source kinds excluded by --student-only: images, generic marketing/blog pages, and file/link
# asset stubs. Student-relevant kinds (policy/calendar/financial/registrar/student_life/library/gateway/
# catalog/docx/spreadsheet/...) are KEPT.
NOISE_SOURCE_KINDS = {"image_asset", "file_asset", "external_public_page", "link_reference"}


def _doc_source_kind(doc) -> str:
    sm = getattr(doc, "source_metadata", None)
    return (getattr(sm, "source_kind", None) if sm else None) or (doc.metadata or {}).get("source_kind") or ""


def _effective_source_kind(doc) -> str:
    """RE-DERIVE the source kind from the URL for ALL VinUni-owned hosts so classifier refinements take
    effect on already-crawled raw WITHOUT a re-crawl (the classifier is the single source of truth at
    ingest). Originally scoped to the expansion subdomains; widened to the whole vinuni.edu.vn domain after
    the 2026-06-24 audit found the main-domain default-drop was silently discarding /people/ leadership
    bios (the President bug) — re-deriving lets the path-aware fix apply without re-crawling. Non-VinUni
    (external) docs keep their stored kind (they are dropped by --vinuni-only regardless)."""
    from urllib.parse import urlparse

    from vinchatbot.app.ingest.normalizer import infer_source_kind

    url = getattr(doc, "source_url", "") or ""
    if urlparse(url).netloc.lower().endswith("vinuni.edu.vn"):
        return infer_source_kind(url, title=getattr(doc, "title", None))
    return _doc_source_kind(doc)


def _report_dropped(dropped) -> None:
    """Make --student-only drops VISIBLE so a future false-drop surfaces in the ingest log instead of
    requiring a fresh audit (the 2026-06-24 /people/ leadership bug went unnoticed precisely because the
    drop was silent). Logs the dropped count by kind and the top dropped first-path sections per VinUni
    host-class — a high-count /people/ or /<unfamiliar-section>/ line is the early-warning that a high-value
    section is being discarded. See LOGS/INGEST_FILTER_AUDIT.md for the keep/drop decision matrix."""
    from collections import Counter
    from urllib.parse import urlparse

    by_kind: Counter = Counter()
    by_section: Counter = Counter()
    for doc in dropped:
        url = getattr(doc, "source_url", "") or ""
        host = urlparse(url).netloc.lower()
        by_kind[_effective_source_kind(doc)] += 1
        if not host.endswith("vinuni.edu.vn"):
            continue
        hc = "main" if host in ("vinuni.edu.vn", "www.vinuni.edu.vn") else host.split(".")[0]
        segs = [s for s in urlparse(url).path.lower().split("/") if s]
        if segs and segs[0] in ("vi", "en") and len(segs) > 1:
            segs = segs[1:]
        by_section[f"{hc}/{segs[0] if segs else '(root)'}/"] += 1
    logger.info("Dropped-by-kind: %s", dict(by_kind.most_common()))
    logger.info(
        "Top dropped VinUni sections (watch for high-value content here): %s",
        [f"{sec}={n}" for sec, n in by_section.most_common(15)],
    )


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        stream=sys.stdout,
    )


def _stamp_policy_metadata(chunks, records) -> int:
    """Propagate policy_code / issued / updated from `policy_listing` records onto the
    policy *text* chunks (matched by detail_url == chunk canonical_url). The rich listing
    metadata is otherwise stranded on listing records that mostly aren't chunked.
    """
    by_url: dict[str, dict] = {}
    for record in records:
        if record.record_type != "policy_listing":
            continue
        data = record.data
        url = (data.get("detail_url") or "").rstrip("/")
        if url and data.get("policy_code"):
            by_url[url] = {
                "policy_code": data.get("policy_code"),
                "issued_date": data.get("date_issued"),
                "updated_date": data.get("date_last_updated"),
            }
    stamped = 0
    for chunk in chunks:
        meta = by_url.get((chunk.metadata.canonical_url or "").rstrip("/"))
        if not meta:
            continue
        if not chunk.metadata.policy_code:
            chunk.metadata.policy_code = meta["policy_code"]
            chunk.metadata.issued_date = chunk.metadata.issued_date or meta["issued_date"]
            chunk.metadata.updated_date = chunk.metadata.updated_date or meta["updated_date"]
            stamped += 1
    return stamped


def _dedup_by_content_hash(chunks):
    """Drop chunks with duplicate content (keep first occurrence). Removes exact
    duplicates such as a policy's HTML and PDF copies that chunk to identical text.
    """
    seen: set[str] = set()
    deduped = []
    for chunk in chunks:
        digest = chunk.metadata.content_hash
        if digest in seen:
            continue
        seen.add(digest)
        deduped.append(chunk)
    return deduped


def main() -> None:
    parser = argparse.ArgumentParser(description="Chunk + index raw documents into the vector store.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--recreate",
        action="store_true",
        help="Drop + rebuild the Qdrant collection (clean re-index, removes stale points). "
        "Use with QDRANT_COLLECTION=<scratch> to avoid touching production.",
    )
    mode.add_argument(
        "--incremental",
        action="store_true",
        help="Cheap re-ingest into an EXISTING collection: re-embed ONLY new/changed chunks (reuse the "
        "stored vectors for unchanged content) and delete stale points. Reconciles the collection to the "
        "full current corpus; aborts if it would delete >50%% (partial-crawl guard). Mutually exclusive "
        "with --recreate.",
    )
    parser.add_argument(
        "--vinuni-only",
        action="store_true",
        help="Index only docs on a VinUni domain (drop external pages the crawler reached via outbound "
        "links — apple.com, other universities, etc.). Keeps the index focused; avoids off-topic noise.",
    )
    parser.add_argument(
        "--student-only",
        action="store_true",
        help="Drop low-value source kinds (images, generic marketing/blog pages, file/link asset stubs); "
        "keep student-relevant docs (policy/calendar/financial/registrar/student-life/library/docx/...). "
        "Use to avoid diluting the index with the marketing site a deep crawl pulls in.",
    )
    args = parser.parse_args()

    configure_logging()
    settings = get_settings()
    logger.info("Loading raw documents from %s", settings.raw_data_dir)
    documents = read_raw_documents(settings.raw_data_dir)
    logger.info("Loaded documents=%s", len(documents))
    if args.vinuni_only:
        before = len(documents)
        documents = [d for d in documents if "vinuni" in ((d.metadata.get("domain") or "").lower())]
        logger.info("Filtered to VinUni-domain docs: %s -> %s (-%s)", before, len(documents), before - len(documents))
    if args.student_only:
        before = len(documents)
        kept, dropped = [], []
        for doc in documents:
            (kept if _effective_source_kind(doc) not in NOISE_SOURCE_KINDS else dropped).append(doc)
        documents = kept
        logger.info(
            "Filtered to student-relevant kinds: %s -> %s (-%s)", before, len(documents), len(dropped)
        )
        _report_dropped(dropped)

    chunks = []
    records = []
    progress_interval = max(1, min(100, len(documents) // 10 or 1))
    for index, document in enumerate(documents, start=1):
        document_chunks = chunk_document(document)
        chunks.extend(document_chunks)
        records.extend(document.structured_records)
        if index == len(documents) or index % progress_interval == 0:
            logger.info(
                "Chunked %s/%s documents chunks=%s structured_records=%s last_type=%s title=%s",
                index,
                len(documents),
                len(chunks),
                len(records),
                document.document_type,
                document.title[:120],
            )

    stamped = _stamp_policy_metadata(chunks, records)
    logger.info("Stamped policy_code onto %s policy chunks from listing records", stamped)

    before = len(chunks)
    chunks = _dedup_by_content_hash(chunks)
    logger.info("Deduped chunks by content hash: %s -> %s (-%s)", before, len(chunks), before - len(chunks))

    records_path = f"{settings.processed_data_dir}/structured_records.json"
    logger.info("Writing structured records=%s path=%s", len(records), records_path)
    write_structured_records(records, records_path)

    chunks_path = f"{settings.processed_data_dir}/chunks.json"
    logger.info("Writing chunks=%s path=%s", len(chunks), chunks_path)
    with open(chunks_path, "w", encoding="utf-8") as handle:
        json.dump([chunk.model_dump() for chunk in chunks], handle, ensure_ascii=False, indent=2)

    logger.info(
        "Indexing chunks=%s backend=%s qdrant_collection=%s",
        len(chunks),
        settings.vector_store_backend,
        settings.qdrant_collection,
    )
    effective_incremental = args.incremental or settings.enable_incremental_ingest
    indexed = index_chunks(chunks, settings, recreate=args.recreate, incremental=args.incremental)
    logger.info(
        "Finished indexing indexed=%s recreate=%s incremental=%s",
        indexed,
        args.recreate,
        effective_incremental,
    )
    summary = {
        "documents": len(documents),
        "chunks": len(chunks),
        "structured_records": len(records),
        "incremental": effective_incremental,
    }
    if effective_incremental:
        # `added` = chunks NEWLY embedded this run; the collection holds ~`chunks` total (unchanged chunks
        # reused their stored vectors). The full add/unchanged/deleted breakdown is in the log line above.
        summary["added"] = indexed
    else:
        summary["indexed"] = indexed
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
