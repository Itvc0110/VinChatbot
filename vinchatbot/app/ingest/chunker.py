from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from vinchatbot.app.core.config import get_settings
from vinchatbot.app.ingest.normalizer import (
    guess_language,
    infer_category,
    normalize_text,
    strip_boilerplate,
)
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
    max_tokens: int = 1024
    overlap_tokens: int = 96
    header_levels: int = 2  # split on # / ## only (fewer, larger sections)


_PageTagged = tuple[str, list[str], int | None]  # (text, section_path, page_number)


def chunk_document(raw: RawDocument, config: ChunkingConfig | None = None) -> list[DocumentChunk]:
    settings = get_settings()
    if config is None:
        config = ChunkingConfig(
            max_tokens=settings.chunk_max_tokens,
            overlap_tokens=settings.chunk_overlap_tokens,
            header_levels=settings.chunk_header_levels,
        )
    content = strip_boilerplate(raw.content)

    category, subcategory = infer_category(raw.source_url, raw.title)
    category = raw.metadata.get("category", category)
    subcategory = raw.metadata.get("subcategory", subcategory)
    original_language = raw.metadata.get("original_language") or guess_language(raw.content)
    source_metadata = raw.source_metadata

    pieces: list[_PageTagged] | None = None
    if settings.enable_markdown_parsing:
        pieces = _split_markdown_prose(content, config)
    if pieces is None:  # markdown disabled or splitter unavailable -> legacy behavior
        pieces = _split_paragraphs_fallback(content, config)

    if not pieces and not raw.structured_records:
        return []

    chunks: list[DocumentChunk] = [
        _build_prose_chunk(
            raw=raw,
            text=text,
            index=index,
            section_path=section_path,
            page_number=page_number,
            category=category,
            subcategory=subcategory,
            original_language=original_language,
            source_metadata=source_metadata,
        )
        for index, (text, section_path, page_number) in enumerate(pieces)
    ]

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


def _build_prose_chunk(
    *,
    raw: RawDocument,
    text: str,
    index: int,
    section_path: list[str],
    page_number: int | None,
    category: str,
    subcategory: str,
    original_language: str,
    source_metadata: Any,
) -> DocumentChunk:
    text = normalize_text(text)
    chunk_id = stable_hash(f"{raw.parent_doc_id}:{index}:{text}")
    section_title = section_path[-1] if section_path else None
    section_id = stable_hash(" > ".join(section_path)) if section_path else None
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
        section_path=section_path,
        section_title=section_title,
        section_level=len(section_path) if section_path else None,
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
    return DocumentChunk(text=text, metadata=metadata)


_PAGE_MARKER_RE = re.compile(r"^trang\s+(\d+)", re.IGNORECASE)


def _page_marker(heading: str) -> int | None:
    match = _PAGE_MARKER_RE.match(heading.strip())
    return int(match.group(1)) if match else None


def _is_only_headers(text: str) -> bool:
    lines = [line for line in text.splitlines() if line.strip()]
    return bool(lines) and all(line.lstrip().startswith("#") for line in lines)


def _split_markdown_prose(content: str, config: ChunkingConfig) -> list[_PageTagged] | None:
    """Header-aware, token-sized splitting via LangChain. Returns None to signal fallback.

    Splits on Markdown headers (capturing the trail as section_path), then sizes each
    section by tokens. `# Trang N` page markers are carried forward as page_number and kept
    out of section_path; header-only fragments are dropped.
    """
    if not content.strip():
        return []
    try:
        from langchain_text_splitters import (
            MarkdownHeaderTextSplitter,
            RecursiveCharacterTextSplitter,
        )
    except ImportError:
        return None
    headers = [("#", "h1"), ("##", "h2"), ("###", "h3"), ("####", "h4")][: max(1, config.header_levels)]
    try:
        md_splitter = MarkdownHeaderTextSplitter(headers, strip_headers=False)
        char_splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
            encoding_name="cl100k_base",
            chunk_size=config.max_tokens,
            chunk_overlap=config.overlap_tokens,
        )
        header_docs = md_splitter.split_text(content)
    except Exception:
        return None

    results: list[_PageTagged] = []
    current_page: int | None = None
    for doc in header_docs:
        trail = [doc.metadata[key] for key in ("h1", "h2", "h3", "h4") if doc.metadata.get(key)]
        for heading in trail:
            page = _page_marker(heading)
            if page is not None:
                current_page = page
        section_path = [heading for heading in trail if _page_marker(heading) is None]
        for piece in char_splitter.split_text(doc.page_content):
            piece = normalize_text(piece)
            for line in piece.splitlines():
                page = _page_marker(line.lstrip("# ").strip())
                if page is not None:
                    current_page = page
            if not piece or _is_only_headers(piece):
                continue
            results.append((piece, list(section_path), current_page))
    return results


def _split_paragraphs_fallback(content: str, config: ChunkingConfig) -> list[_PageTagged]:
    """Legacy char-based paragraph accumulation (used when markdown parsing is disabled)."""
    paragraphs = _paragraphs_with_sections(content)
    results: list[_PageTagged] = []
    buffer: list[str] = []
    section_path: list[str] = []
    active_section: list[str] = []
    page_number: int | None = None

    def flush() -> None:
        nonlocal buffer
        text = normalize_text("\n\n".join(buffer))
        if text:
            results.append((text, list(section_path or active_section), page_number))
            buffer = [text[-config.overlap_chars :]] if config.overlap_chars > 0 and text[-config.overlap_chars :].strip() else []
        else:
            buffer = []

    for paragraph, heading_path, paragraph_page in paragraphs:
        if heading_path:
            active_section = heading_path
            section_path = heading_path
        if paragraph_page is not None:
            page_number = paragraph_page
        if buffer and len("\n\n".join(buffer)) + len(paragraph) > config.max_chars:
            flush()
        buffer.append(paragraph)
    flush()
    return results


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
            event_type=data.get("event_type"),
            fee_type=data.get("fee_type"),
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
        # Index an image only when it carries real signal: OCR text or a substantive
        # caption. Bare alt-text / nearby-text descriptions are low value for text Q&A and
        # were ~34% of the index, so they are dropped (Phase 2 metadata cleanup).
        ocr_text = normalize_text(str(data.get("ocr_text") or ""))
        caption = normalize_text(str(data.get("caption") or ""))
        if len(ocr_text) >= 20:
            return normalize_text(f"Image OCR text: {ocr_text}")
        if len(caption) >= 40:
            description = normalize_text(str(data.get("description") or caption))
            return f"Image asset: {description}" if len(description) >= 20 else None
        return None
    if record.record_type == "calendar_event":
        return _calendar_event_to_text(data)
    if record.record_type == "fee_record":
        return _fee_record_to_text(data)
    return None


def _calendar_event_to_text(data: dict[str, Any]) -> str | None:
    event = normalize_text(str(data.get("event_name") or ""))
    if len(event) < 4:
        return None
    term = (data.get("term") or "").strip()
    year = (data.get("academic_year") or "").strip()
    scope = " ".join(part for part in (term, year) if part)
    date_text = data.get("date_text_original") or data.get("date_start") or ""
    iso = data.get("date_start_iso") or ""
    if iso and data.get("date_end_iso"):
        iso = f"{iso} to {data.get('date_end_iso')}"
    date_str = f"{date_text} ({iso})".strip() if iso else str(date_text)
    parts = [f"Academic calendar event{f' — {scope}' if scope else ''}: {event}."]
    if date_str.strip():
        parts.append(f"Date: {date_str}.")
    if data.get("event_type"):
        parts.append(f"Event type: {data['event_type']}.")
    return normalize_text(" ".join(parts))


def _fee_record_to_text(data: dict[str, Any]) -> str | None:
    conditions = normalize_text(str(data.get("conditions") or ""))
    name = normalize_text(str(data.get("fee_name") or ""))
    amount = data.get("amount_text_original") or (
        f"{data.get('amount')} {data.get('currency') or ''}".strip() if data.get("amount") else ""
    )
    body = conditions if len(conditions) >= 12 else name
    if not body and not amount:
        return None
    fee_type = data.get("fee_type")
    text = f"Student fee{f' ({fee_type})' if fee_type else ''}: {body}".strip()
    if amount and amount not in body:
        text = f"{text} Amount: {amount}."
    text = normalize_text(text)
    return text if len(text) >= 12 else None


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
