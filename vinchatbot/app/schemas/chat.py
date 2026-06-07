from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class RetrievalFilters(BaseModel):
    document_type: str | None = None
    category: str | None = None
    subcategory: str | None = None
    academic_year: str | None = None
    term: str | None = None
    original_language: str | None = None

    def compact(self) -> dict[str, str]:
        return {key: value for key, value in self.model_dump().items() if value}


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    conversation_id: str = Field(default="default", min_length=1)
    filters: RetrievalFilters | None = None


class Citation(BaseModel):
    source_url: str
    title: str
    section: str | None = None
    page_number: int | None = None
    excerpt: str
    score: float | None = None


class ChatResponse(BaseModel):
    answer: str
    citations: list[Citation] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    tool_trace: list[dict[str, Any]] = Field(default_factory=list)
    needs_human_review: bool = False


class IngestRunRequest(BaseModel):
    urls: list[str] | None = None
    force: bool = False


class IngestRunResponse(BaseModel):
    crawled_documents: int
    indexed_chunks: int
    skipped_documents: int = 0
    sources: list[str] = Field(default_factory=list)

