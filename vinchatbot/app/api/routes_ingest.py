from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException, status

from vinchatbot.app.core.config import get_settings
from vinchatbot.app.ingest.chunker import chunk_document
from vinchatbot.app.ingest.crawler import (
    VinUniCrawler,
    read_raw_documents,
    write_crawl_manifest,
    write_crawl_coverage_report,
    write_link_references,
    write_raw_documents,
    write_structured_records,
)
from vinchatbot.app.ingest.indexer import index_chunks
from vinchatbot.app.schemas.chat import IngestRunRequest, IngestRunResponse
from vinchatbot.app.schemas.document import DocumentChunk, SourceSummary

router = APIRouter(tags=["ingest"])


@router.post("/ingest/run", response_model=IngestRunResponse)
async def run_ingest(request: IngestRunRequest) -> IngestRunResponse:
    settings = get_settings()
    try:
        crawler = VinUniCrawler(settings)
        crawl_result = await crawler.crawl_full(request.urls, force=request.force)
        raw_documents = crawl_result.documents
        write_raw_documents(raw_documents, settings.raw_data_dir)
        processed_dir = Path(settings.processed_data_dir)
        write_crawl_manifest(crawl_result.manifest_entries, processed_dir / "crawl_manifest.json")
        write_link_references(crawl_result.link_references, processed_dir / "link_references.json")
        write_structured_records(crawl_result.structured_records, processed_dir / "structured_records.json")
        write_crawl_coverage_report(
            raw_documents,
            crawl_result.manifest_entries,
            crawl_result.link_references,
            processed_dir / "crawl_coverage_report.json",
        )

        chunks: list[DocumentChunk] = []
        skipped = 0
        for document in raw_documents:
            document_chunks = chunk_document(document)
            if not document_chunks:
                skipped += 1
                continue
            chunks.extend(document_chunks)

        _write_processed_chunks(chunks, settings.processed_data_dir)
        indexed = index_chunks(chunks, settings)
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    return IngestRunResponse(
        crawled_documents=len(raw_documents),
        indexed_chunks=indexed,
        skipped_documents=skipped,
        sources=[document.source_url for document in raw_documents],
    )


@router.get("/sources", response_model=list[SourceSummary])
async def list_sources() -> list[SourceSummary]:
    settings = get_settings()
    raw_documents = read_raw_documents(settings.raw_data_dir)
    summaries: list[SourceSummary] = []
    for document in raw_documents:
        summaries.append(
            SourceSummary(
                source_url=document.source_url,
                document_title=document.title,
                document_type=document.document_type,
                content_hash=document.content_hash,
                crawled_at=document.fetched_at,
                chunk_count=len(chunk_document(document)),
            )
        )
    return summaries


def _write_processed_chunks(chunks: list[DocumentChunk], output_dir: str) -> None:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    payload = [chunk.model_dump() for chunk in chunks]
    (output_path / "chunks.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
