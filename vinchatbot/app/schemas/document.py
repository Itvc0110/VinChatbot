from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

DocumentType = Literal[
    "html",
    "pdf",
    "calendar",
    "policy",
    "gateway_page",
    "policy_listing",
    "policy_html",
    "policy_pdf",
    "calendar_page",
    "calendar_pdf",
    "financial_policy",
    "academic_catalog",
    "program_spec",
    "registrar_page",
    "library_page",
    "student_life_page",
    "admissions_page",
    "program_page",
    "faq_page",
    "scholarship_page",
    "profile_page",
    "about_page",
    "external_public_page",
    "markdown",
    "spreadsheet",
    "csv",
    "image_asset",
    "file_asset",
    "pdf_ocr",
    "link_reference",
    "unknown",
]

RecordType = Literal[
    "calendar_event",
    "fee_record",
    "policy_listing",
    "program",
    "link_reference",
    "image_asset",
    "ocr_text",
    "table_record",
    "spreadsheet_row",
    "file_asset",
]


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def stable_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class CrawlTarget(BaseModel):
    source_url: str
    parent_url: str | None = None
    crawl_depth: int = 0
    anchor_text: str | None = None
    link_context: str | None = None
    discovered_from: str | None = None
    source_kind_hint: str | None = None


class SourceDocumentMetadata(BaseModel):
    source_id: str
    source_url: str
    final_url: str
    canonical_url: str
    source_kind: str = "unknown"
    domain: str = "unknown"
    domain_type: str = "unknown"
    source_trust: str = "unknown"
    parent_url: str | None = None
    crawl_depth: int = 0
    anchor_text: str | None = None
    link_context: str | None = None
    discovered_from: str | None = None
    http_status: int | None = None
    content_type: str | None = None
    mime_type: str | None = None
    file_size_bytes: int | None = None
    etag: str | None = None
    last_modified_header: str | None = None
    fetched_at: str = Field(default_factory=utc_now_iso)
    content_hash: str | None = None
    robots_allowed: bool = True
    requires_login: bool = False
    noindex: bool = False
    access_level: str = "public"
    parser_name: str = "unknown"
    parser_version: str = "v1"
    crawl_run_id: str | None = None


class CrawlManifestEntry(BaseModel):
    source_id: str
    source_url: str
    final_url: str
    canonical_url: str
    source_kind: str = "unknown"
    domain: str = "unknown"
    crawl_depth: int = 0
    http_status: int | None = None
    fetched_at: str = Field(default_factory=utc_now_iso)
    content_hash: str | None = None
    parser_name: str = "unknown"
    parser_version: str = "v1"
    indexed: bool = False
    skipped: bool = False
    skip_reason: str | None = None
    crawl_run_id: str | None = None


class LinkReference(BaseModel):
    source_url: str
    target_url: str
    anchor_text: str | None = None
    link_context: str | None = None
    section_path: list[str] = Field(default_factory=list)
    discovered_from: str | None = None
    domain: str = "unknown"
    domain_type: str = "unknown"
    source_kind: str = "link_reference"
    source_trust: str = "unknown"
    requires_login: bool = False
    robots_allowed: bool | None = None
    should_crawl: bool = False
    reason: str | None = None


class StructuredRecord(BaseModel):
    record_id: str
    record_type: RecordType
    parent_doc_id: str
    source_url: str
    title: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class DocumentMetadata(BaseModel):
    """Metadata stored with every retrievable chunk.

    Some fields can be unknown for a source, but the key still exists so filters
    and citation rendering remain stable across crawls.
    """

    source_url: str
    canonical_url: str
    document_title: str
    document_type: DocumentType = "unknown"
    source_id: str | None = None
    source_kind: str = "unknown"
    domain: str | None = None
    domain_type: str | None = None
    source_trust: str | None = None
    category: str = "unknown"
    subcategory: str = "unknown"
    original_language: str = "vi"
    answer_language: str = "vi"
    issued_date: str | None = None
    updated_date: str | None = None
    effective_date: str | None = None
    academic_year: str | None = None
    term: str | None = None
    cohort: str | None = None
    college: str | None = None
    program: str | None = None
    page_number: int | None = None
    section_id: str | None = None
    section_path: list[str] = Field(default_factory=list)
    section_title: str | None = None
    section_level: int | None = None
    table_id: str | None = None
    row_index: int | None = None
    policy_code: str | None = None
    reference_number: str | None = None
    document_status: str | None = None
    issuing_unit: str | None = None
    applying_for: str | None = None
    security_classification: str | None = None
    chunk_id: str
    parent_doc_id: str
    content_hash: str
    crawled_at: str = Field(default_factory=utc_now_iso)
    audience: str = "student"
    entities: list[str] = Field(default_factory=list)
    relation_hints: list[str] = Field(default_factory=list)
    record_type: str | None = None
    event_type: str | None = None
    fee_type: str | None = None
    asset_url: str | None = None
    asset_type: str | None = None
    mime_type: str | None = None
    filename: str | None = None
    description_source: str | None = None
    ocr_engine: str | None = None
    ocr_model: str | None = None
    ocr_lang: str | None = None
    ocr_confidence: float | None = None
    needs_ocr: bool | None = None

    @field_validator("source_url", "canonical_url", "document_title", "chunk_id", "parent_doc_id")
    @classmethod
    def required_non_empty(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("required metadata field cannot be empty")
        return value.strip()

    def citation_label(self) -> str:
        location = ""
        if self.page_number:
            location = f", trang {self.page_number}"
        elif self.section_path:
            location = f", mục {' > '.join(self.section_path[-2:])}"
        return f"{self.document_title}{location}"


class RawDocument(BaseModel):
    source_url: str
    canonical_url: str
    title: str
    document_type: DocumentType = "unknown"
    content: str
    fetched_at: str = Field(default_factory=utc_now_iso)
    metadata: dict[str, Any] = Field(default_factory=dict)
    source_metadata: SourceDocumentMetadata | None = None
    structured_records: list[StructuredRecord] = Field(default_factory=list)

    @property
    def parent_doc_id(self) -> str:
        return stable_hash(self.canonical_url)

    @property
    def content_hash(self) -> str:
        return stable_hash(self.content)


class DocumentChunk(BaseModel):
    text: str
    metadata: DocumentMetadata

    @field_validator("text")
    @classmethod
    def text_must_not_be_empty(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("chunk text cannot be empty")
        return value.strip()

    def to_langchain_metadata(self) -> dict[str, Any]:
        return self.metadata.model_dump()


class CalendarEvent(BaseModel):
    event_name: str
    date_start: str
    date_end: str | None = None
    event_type: str | None = None
    date_text_original: str | None = None
    date_start_iso: str | None = None
    date_end_iso: str | None = None
    academic_year: str | None = None
    term: str | None = None
    source_url: str
    page_number: int | None = None


class SourceSummary(BaseModel):
    source_url: str
    document_title: str
    document_type: DocumentType
    content_hash: str
    crawled_at: str
    chunk_count: int = 0
