import asyncio

from vinchatbot.app.ingest.chunker import chunk_document
from vinchatbot.app.ingest.parsers import extract_calendar_events
from vinchatbot.app.rag.retriever import InMemoryRetriever
from vinchatbot.app.schemas.document import RawDocument


def test_in_memory_retriever_returns_filtered_calendar_citation():
    async def run_test():
        raw = RawDocument(
            source_url="https://policy.vinuni.edu.vn/calendar.pdf",
            canonical_url="https://policy.vinuni.edu.vn/calendar.pdf",
            title="Academic Calendar",
            document_type="pdf",
            content="# Academic Calendar\n\nFall 2025 Instruction Begins - 15 September",
        )
        chunks = chunk_document(raw)
        retriever = InMemoryRetriever(chunks)

        results = await retriever.search(
            "Fall instruction begins",
            filters={"category": "academic", "subcategory": "calendar"},
        )

        assert results
        assert results[0].metadata.source_url == raw.source_url
        assert "15 September" in results[0].text

    asyncio.run(run_test())


def test_calendar_parser_extracts_deadline_like_events():
    raw = RawDocument(
        source_url="https://policy.vinuni.edu.vn/calendar.pdf",
        canonical_url="https://policy.vinuni.edu.vn/calendar.pdf",
        title="Academic Calendar",
        document_type="pdf",
        content=(
            "# Trang 1\n\n"
            "Fall 2025 Instruction Begins - 15 September\n"
            "Course Drop Deadline 3/10\n"
            "Unrelated campus text"
        ),
        metadata={"academic_year": "2025-2026"},
    )

    events = extract_calendar_events(raw)

    assert len(events) >= 2
    assert any("Drop Deadline" in event.event_name for event in events)
    assert all(event.source_url == raw.source_url for event in events)

