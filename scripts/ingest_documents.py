from __future__ import annotations

import json
import logging
import sys

from vinchatbot.app.core.config import get_settings
from vinchatbot.app.ingest.chunker import chunk_document
from vinchatbot.app.ingest.crawler import read_raw_documents, write_structured_records
from vinchatbot.app.ingest.indexer import index_chunks

logger = logging.getLogger(__name__)


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
    configure_logging()
    settings = get_settings()
    logger.info("Loading raw documents from %s", settings.raw_data_dir)
    documents = read_raw_documents(settings.raw_data_dir)
    logger.info("Loaded documents=%s", len(documents))

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
    indexed = index_chunks(chunks, settings)
    logger.info("Finished indexing indexed=%s", indexed)
    print(
        json.dumps(
            {
                "documents": len(documents),
                "chunks": len(chunks),
                "structured_records": len(records),
                "indexed": indexed,
            }
        )
    )


if __name__ == "__main__":
    main()
