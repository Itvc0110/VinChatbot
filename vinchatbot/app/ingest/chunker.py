from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from vinchatbot.app.ingest.normalizer import guess_language, infer_category, normalize_text
from vinchatbot.app.schemas.document import (
    DocumentChunk,
    DocumentMetadata,
    RawDocument,
    StructuredRecord,
    stable_hash,
)


@dataclass(frozen=True)
class ChunkingConfig:
    max_chars: int = 2800
    overlap_chars: int = 350


def chunk_document(raw: RawDocument, config: ChunkingConfig | None = None) -> list[DocumentChunk]:
    config = config or ChunkingConfig()
    paragraphs = _paragraphs_with_sections(raw.content)
    if not paragraphs and not raw.structured_records:
        return []

    category, subcategory = infer_category(raw.source_url, raw.title)
    category = raw.metadata.get("category", category)
    subcategory = raw.metadata.get("subcategory", subcategory)
    original_language = raw.metadata.get("original_language") or guess_language(raw.content)
    source_metadata = raw.source_metadata

    chunks: list[DocumentChunk] = []
    buffer: list[str] = []
    section_path: list[str] = []
    active_section: list[str] = []
    page_number: int | None = None

    def flush() -> None:
        nonlocal buffer, chunks
        text = normalize_text("\n\n".join(buffer))
        if not text:
            buffer = []
            return
        chunk_id = stable_hash(f"{raw.parent_doc_id}:{len(chunks)}:{text}")
        effective_section_path = list(section_path or active_section)
        section_title = effective_section_path[-1] if effective_section_path else None
        section_id = stable_hash(" > ".join(effective_section_path)) if effective_section_path else None
        metadata = DocumentMetadata(
            source_url=raw.source_url,
            canonical_url=raw.canonical_url,
            document_title=raw.title,
            document_type=raw.document_type,
            source_id=raw.metadata.get("source_id") or (source_metadata.source_id if source_metadata else None),
            source_kind=raw.metadata.get("source_kind", "unknown"),
            domain=raw.metadata.get("domain") or (source_metadata.domain if source_metadata else None),
            domain_type=raw.metadata.get("domain_type") or (source_metadata.domain_type if source_metadata else None),
            source_trust=raw.metadata.get("source_trust") or (source_metadata.source_trust if source_metadata else None),
            category=category,
            subcategory=subcategory,
            original_language=original_language,
            answer_language="vi",
            issued_date=raw.metadata.get("issued_date"),
            updated_date=raw.metadata.get("updated_date"),
            effective_date=raw.metadata.get("effective_date"),
            academic_year=raw.metadata.get("academic_year"),
            term=raw.metadata.get("term"),
            cohort=raw.metadata.get("cohort"),
            college=raw.metadata.get("college"),
            program=raw.metadata.get("program"),
            page_number=page_number,
            section_id=section_id,
            section_path=effective_section_path,
            section_title=section_title,
            section_level=len(effective_section_path) if effective_section_path else None,
            table_id=raw.metadata.get("table_id"),
            row_index=raw.metadata.get("row_index"),
            policy_code=raw.metadata.get("policy_code"),
            reference_number=raw.metadata.get("reference_number"),
            document_status=raw.metadata.get("document_status"),
            issuing_unit=raw.metadata.get("issuing_unit"),
            applying_for=raw.metadata.get("applying_for"),
            security_classification=raw.metadata.get("security_classification"),
            chunk_id=chunk_id,
            parent_doc_id=raw.parent_doc_id,
            content_hash=stable_hash(text),
            crawled_at=raw.fetched_at,
            audience=raw.metadata.get("audience", "student"),
            entities=list(raw.metadata.get("entities", [])),
            relation_hints=list(raw.metadata.get("relation_hints", [])),
        )
        chunks.append(DocumentChunk(text=text, metadata=metadata))
        if config.overlap_chars > 0:
            overlap = text[-config.overlap_chars :]
            buffer = [overlap] if overlap.strip() else []
        else:
            buffer = []

    for paragraph, heading_path, paragraph_page in paragraphs:
        if heading_path:
            active_section = heading_path
            section_path = heading_path
        if paragraph_page is not None:
            page_number = paragraph_page
        paragraph_len = len(paragraph)
        current_len = len("\n\n".join(buffer))
        if buffer and current_len + paragraph_len > config.max_chars:
            flush()
        buffer.append(paragraph)
    flush()

    chunks.extend(
        _chunks_from_structured_records(
            raw=raw,
            records=raw.structured_records,
            starting_index=len(chunks),
            category=category,
            subcategory=subcategory,
            original_language=original_language,
        )
    )

    return chunks


def _chunks_from_structured_records(
    *,
    raw: RawDocument,
    records: list[StructuredRecord],
    starting_index: int,
    category: str,
    subcategory: str,
    original_language: str,
) -> list[DocumentChunk]:
    chunks: list[DocumentChunk] = []
    source_metadata = raw.source_metadata
    for offset, record in enumerate(records):
        text = _record_to_chunk_text(record)
        if not text:
            continue
        data = record.data
        section_path = _record_section_path(data, record.metadata)
        section_title = section_path[-1] if section_path else None
        section_id = stable_hash(" > ".join(section_path)) if section_path else None
        chunk_id = stable_hash(f"{record.record_id}:{starting_index + offset}:{text}")
        metadata = DocumentMetadata(
            source_url=raw.source_url,
            canonical_url=raw.canonical_url,
            document_title=record.title or raw.title,
            document_type=raw.document_type,
            source_id=raw.metadata.get("source_id") or (source_metadata.source_id if source_metadata else None),
            source_kind=record.record_type,
            domain=raw.metadata.get("domain") or (source_metadata.domain if source_metadata else None),
            domain_type=raw.metadata.get("domain_type") or (source_metadata.domain_type if source_metadata else None),
            source_trust=raw.metadata.get("source_trust") or (source_metadata.source_trust if source_metadata else None),
            category=category,
            subcategory=subcategory,
            original_language=original_language,
            answer_language="vi",
            issued_date=raw.metadata.get("issued_date"),
            updated_date=raw.metadata.get("updated_date"),
            effective_date=raw.metadata.get("effective_date"),
            academic_year=raw.metadata.get("academic_year") or data.get("academic_year"),
            term=raw.metadata.get("term") or data.get("term"),
            cohort=raw.metadata.get("cohort") or data.get("cohort"),
            college=raw.metadata.get("college") or data.get("college"),
            program=raw.metadata.get("program") or data.get("program_name"),
            page_number=data.get("page_number") or record.metadata.get("page_number"),
            section_id=section_id,
            section_path=section_path,
            section_title=section_title,
            section_level=len(section_path) if section_path else None,
            table_id=data.get("table_id") or record.metadata.get("table_id"),
            row_index=data.get("row_index") or record.metadata.get("row_index"),
            policy_code=raw.metadata.get("policy_code") or data.get("policy_code"),
            reference_number=raw.metadata.get("reference_number") or data.get("reference_number"),
            document_status=raw.metadata.get("document_status"),
            issuing_unit=raw.metadata.get("issuing_unit"),
            applying_for=raw.metadata.get("applying_for"),
            security_classification=raw.metadata.get("security_classification"),
            chunk_id=chunk_id,
            parent_doc_id=raw.parent_doc_id,
            content_hash=stable_hash(text),
            crawled_at=raw.fetched_at,
            audience=raw.metadata.get("audience", "student"),
            entities=list(raw.metadata.get("entities", [])),
            relation_hints=list(raw.metadata.get("relation_hints", [])),
            record_type=record.record_type,
            asset_url=data.get("asset_url"),
            asset_type=data.get("asset_type"),
            mime_type=data.get("mime_type"),
            filename=data.get("filename"),
            description_source=data.get("description_source"),
            ocr_engine=data.get("ocr_engine"),
            ocr_model=data.get("ocr_model"),
            ocr_lang=data.get("ocr_lang"),
            ocr_confidence=data.get("ocr_confidence"),
            needs_ocr=data.get("needs_ocr"),
        )
        chunks.append(DocumentChunk(text=text, metadata=metadata))
    return chunks


def _record_to_chunk_text(record: StructuredRecord) -> str | None:
    data = record.data
    if record.record_type == "ocr_text":
        ocr_text = normalize_text(str(data.get("ocr_text") or ""))
        if len(ocr_text) < 20:
            return None
        return normalize_text(f"OCR text from {data.get('asset_url') or record.source_url}:\n{ocr_text}")
    if record.record_type == "table_record":
        rag_text = normalize_text(str(data.get("rag_text") or ""))
        return rag_text if len(rag_text) >= 20 else None
    if record.record_type == "spreadsheet_row":
        rag_text = normalize_text(str(data.get("rag_text") or ""))
        return rag_text if len(rag_text) >= 20 else None
    if record.record_type == "image_asset":
        has_text_context = any(
            data.get(key)
            for key in ("alt_text", "caption", "nearby_text", "link_context", "ocr_text")
        )
        if not has_text_context:
            return None
        description = normalize_text(str(data.get("description") or ""))
        return f"Image asset: {description}" if len(description) >= 20 else None
    return None


def _record_section_path(data: dict[str, Any], metadata: dict[str, Any]) -> list[str]:
    raw_path = data.get("section_path") or metadata.get("section_path") or []
    if isinstance(raw_path, list):
        return [str(item) for item in raw_path if str(item).strip()]
    if isinstance(raw_path, str) and raw_path.strip():
        return [raw_path.strip()]
    return []


def _paragraphs_with_sections(text: str) -> list[tuple[str, list[str], int | None]]:
    items: list[tuple[str, list[str], int | None]] = []
    section_stack: list[str] = []
    current_page: int | None = None

    for raw_part in text.split("\n\n"):
        part = normalize_text(raw_part)
        if not part:
            continue
        if part.startswith("#"):
            heading_text = part.lstrip("#").strip()
            level = max(1, min(6, len(part) - len(part.lstrip("#"))))
            if heading_text.lower().startswith("trang "):
                try:
                    current_page = int(heading_text.split()[1])
                except (IndexError, ValueError):
                    current_page = current_page
            section_stack = section_stack[: level - 1]
            section_stack.append(heading_text)
            items.append((part, list(section_stack), current_page))
            continue
        items.append((part, [], current_page))
    return items
