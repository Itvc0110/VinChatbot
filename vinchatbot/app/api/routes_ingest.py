from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel

from vinchatbot.app.core.config import get_settings
from vinchatbot.app.dependencies.auth import require_roles
from vinchatbot.app.ingest.chunker import chunk_document
from vinchatbot.app.ingest.crawler import (
    VinUniCrawler,
    read_raw_documents,
    write_crawl_coverage_report,
    write_crawl_manifest,
    write_link_references,
    write_raw_documents,
    write_structured_records,
)
from vinchatbot.app.ingest.indexer import index_chunks
from vinchatbot.app.ingest.parsers import parse_docx, parse_html, parse_pdf_bytes
from vinchatbot.app.repositories.auth import AuthenticatedUser
from vinchatbot.app.schemas.chat import IngestRunRequest, IngestRunResponse
from vinchatbot.app.schemas.document import DocumentChunk, RawDocument, SourceSummary

router = APIRouter(tags=["ingest"])

# Knowledge Base ingestion is an admin-only operation (crawl a URL, upload a file, list sources).
AdminUser = Annotated[
    AuthenticatedUser,
    Depends(require_roles("global_admin", "institute_admin", "staff")),
]

# Admin-uploaded files get a stable, namespaced pseudo-URL (not navigable) used as the source id.
UPLOAD_MAX_BYTES = 50 * 1024 * 1024  # 50 MB — matches the upload form's hint
_UPLOAD_EXTENSIONS = {".pdf", ".docx"}
# Map the UI category labels onto the backend metadata taxonomy used for retrieval filtering.
_CATEGORY_MAP = {
    "academic": "academic",
    "tuition": "student_affairs",
    "events": "events",
    "student services": "student_services",
    "schedule": "academic",
}


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "general"


PREVIEW_MAX_CHARS = 6000  # cap the text returned for admin review (the full doc is still indexed)


class IngestPreviewResponse(BaseModel):
    """Real extracted-text preview for the admin review step (parse only — no embedding/upsert)."""

    title: str
    document_type: str
    char_count: int
    estimated_chunks: int
    preview_text: str
    truncated: bool


def _raw_from_file(content: bytes, ext: str, source_url: str, title: str | None) -> RawDocument:
    if ext == ".pdf":
        return parse_pdf_bytes(content, source_url, title=title)
    return parse_docx(content, source_url)


def _raw_from_fetched_url(content: bytes, content_type: str, source_url: str) -> RawDocument:
    lowered = (content_type or "").lower()
    if "pdf" in lowered or source_url.lower().endswith(".pdf"):
        return parse_pdf_bytes(content, source_url)
    return parse_html(content.decode("utf-8", errors="ignore"), source_url)


@router.post("/ingest/run", response_model=IngestRunResponse)
async def run_ingest(request: IngestRunRequest, current_user: AdminUser) -> IngestRunResponse:
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


@router.post("/ingest/upload", response_model=IngestRunResponse)
async def upload_ingest(
    current_user: AdminUser,
    file: UploadFile = File(...),
    category: str | None = Form(default=None),
    title: str | None = Form(default=None),
) -> IngestRunResponse:
    """Admin upload of a single PDF/DOCX into the Knowledge Base.

    Reuses the real ingestion pipeline (parse → chunk → embed → upsert to the vector DB) so the
    document becomes retrievable by Vinnie, exactly like a crawled URL. Synchronous, like
    /ingest/run; the parse/embed/upsert work runs in a threadpool to avoid blocking the loop.
    """
    settings = get_settings()
    filename = file.filename or "document"
    ext = Path(filename).suffix.lower()
    if ext not in _UPLOAD_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Only PDF (.pdf) and Word (.docx) files are supported.",
        )

    content = await file.read()
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The uploaded file is empty.",
        )
    if len(content) > UPLOAD_MAX_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File exceeds the 50 MB limit.",
        )

    clean_title = (title or "").strip() or Path(filename).stem
    category_label = (category or "").strip()
    source_url = f"upload://{_slugify(category_label or 'general')}/{_slugify(Path(filename).stem)}{ext}"

    def _process() -> tuple[RawDocument, int]:
        raw = _raw_from_file(content, ext, source_url, clean_title)
        # Honor the admin-entered title + category (parsers infer their own from the synthetic URL).
        raw.title = clean_title
        raw.metadata["document_title"] = clean_title
        mapped = _CATEGORY_MAP.get(category_label.lower())
        if mapped:
            raw.metadata["category"] = mapped
        chunks = chunk_document(raw)
        if not chunks:
            raise ValueError("no_text")
        # Persist the raw doc so it appears in GET /sources, then embed + upsert to the vector DB.
        write_raw_documents([raw], settings.raw_data_dir)
        indexed = index_chunks(chunks, settings)
        return raw, indexed

    try:
        raw, indexed = await run_in_threadpool(_process)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No extractable text was found (a scanned PDF may require OCR).",
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    return IngestRunResponse(
        crawled_documents=1,
        indexed_chunks=indexed,
        skipped_documents=0,
        sources=[raw.source_url],
    )


@router.post("/ingest/preview", response_model=IngestPreviewResponse)
async def preview_ingest(
    current_user: AdminUser,
    file: UploadFile | None = File(default=None),
    url: str | None = Form(default=None),
    title: str | None = Form(default=None),
) -> IngestPreviewResponse:
    """Parse a file/URL and return the extracted text for admin review — WITHOUT embedding or
    indexing. This powers the "review extracted content" step before the admin approves & indexes.
    """
    clean_title = (title or "").strip()

    if file is not None and file.filename:
        ext = Path(file.filename).suffix.lower()
        if ext not in _UPLOAD_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail="Only PDF (.pdf) and Word (.docx) files are supported.",
            )
        content = await file.read()
        if not content:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="The uploaded file is empty.")
        if len(content) > UPLOAD_MAX_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="File exceeds the 50 MB limit.",
            )
        source_url = f"upload://preview/{_slugify(Path(file.filename).stem)}{ext}"
        raw = await run_in_threadpool(_raw_from_file, content, ext, source_url, clean_title or None)
    elif url and url.strip():
        target = url.strip()
        try:
            async with httpx.AsyncClient(
                timeout=30.0,
                follow_redirects=True,
                headers={"User-Agent": "VinChatbot/admin-preview"},
            ) as client:
                response = await client.get(target)
                response.raise_for_status()
                content = response.content
                content_type = response.headers.get("content-type", "")
        except httpx.HTTPError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Could not fetch the URL: {exc}",
            ) from exc
        if len(content) > UPLOAD_MAX_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="The fetched page exceeds the 50 MB limit.",
            )
        raw = await run_in_threadpool(_raw_from_fetched_url, content, content_type, target)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide a file or a URL to preview.",
        )

    text = (raw.content or "").strip()
    if not text:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No extractable text was found (a scanned PDF may require OCR).",
        )
    estimated_chunks = await run_in_threadpool(lambda: len(chunk_document(raw)))

    return IngestPreviewResponse(
        title=clean_title or raw.title,
        document_type=str(raw.document_type),
        char_count=len(text),
        estimated_chunks=estimated_chunks,
        preview_text=text[:PREVIEW_MAX_CHARS],
        truncated=len(text) > PREVIEW_MAX_CHARS,
    )


@router.get("/sources", response_model=list[SourceSummary])
async def list_sources(current_user: AdminUser) -> list[SourceSummary]:
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
