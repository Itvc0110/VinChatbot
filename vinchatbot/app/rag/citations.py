from __future__ import annotations

from collections.abc import Iterable

from vinchatbot.app.schemas.chat import Citation
from vinchatbot.app.schemas.document import DocumentChunk, DocumentMetadata


def excerpt(text: str, max_chars: int = 420) -> str:
    text = " ".join(text.split())
    if len(text) <= max_chars:
        return text
    return f"{text[: max_chars - 1].rstrip()}..."


def citation_from_chunk(chunk: DocumentChunk, score: float | None = None) -> Citation:
    metadata = chunk.metadata
    section = " > ".join(metadata.section_path) if metadata.section_path else None
    return Citation(
        source_url=metadata.source_url,
        title=metadata.document_title,
        section=section,
        page_number=metadata.page_number,
        excerpt=excerpt(chunk.text),
        score=score,
    )


def citation_from_langchain_doc(doc, score: float | None = None) -> Citation:
    metadata = DocumentMetadata.model_validate(doc.metadata)
    section = " > ".join(metadata.section_path) if metadata.section_path else None
    return Citation(
        source_url=metadata.source_url,
        title=metadata.document_title,
        section=section,
        page_number=metadata.page_number,
        excerpt=excerpt(doc.page_content),
        score=score,
    )


def dedupe_citations(citations: Iterable[Citation]) -> list[Citation]:
    seen: set[tuple[str, str | None, int | None]] = set()
    deduped: list[Citation] = []
    for citation in citations:
        key = (citation.source_url, citation.section, citation.page_number)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(citation)
    return deduped

