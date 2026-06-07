from __future__ import annotations

from dataclasses import dataclass

from vinchatbot.app.ingest.normalizer import guess_language, infer_category, normalize_text
from vinchatbot.app.schemas.document import DocumentChunk, DocumentMetadata, RawDocument, stable_hash


@dataclass(frozen=True)
class ChunkingConfig:
    max_chars: int = 2800
    overlap_chars: int = 350


def chunk_document(raw: RawDocument, config: ChunkingConfig | None = None) -> list[DocumentChunk]:
    config = config or ChunkingConfig()
    paragraphs = _paragraphs_with_sections(raw.content)
    if not paragraphs:
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

    return chunks


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
