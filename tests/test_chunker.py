from vinchatbot.app.ingest.chunker import ChunkingConfig, chunk_document
from vinchatbot.app.schemas.document import RawDocument


def test_chunker_preserves_source_heading_and_page_metadata():
    raw = RawDocument(
        source_url="https://policy.vinuni.edu.vn/wp-content/uploads/calendar.pdf",
        canonical_url="https://policy.vinuni.edu.vn/wp-content/uploads/calendar.pdf",
        title="VinUni Academic Calendar",
        document_type="pdf",
        content=(
            "# Trang 2\n\n"
            "# Academic Calendar\n\n"
            "Fall 2025 Instruction Begins - 15 September\n\n"
            "Course Drop Deadline 3/10"
        ),
        metadata={"academic_year": "2025-2026"},
    )

    chunks = chunk_document(raw, ChunkingConfig(max_chars=400, overlap_chars=0))

    assert chunks
    assert chunks[0].metadata.source_url == raw.source_url
    assert chunks[0].metadata.page_number == 2
    assert chunks[0].metadata.section_path[-1] == "Academic Calendar"
    assert chunks[0].metadata.academic_year == "2025-2026"
    assert chunks[0].metadata.category == "academic"
    assert chunks[0].metadata.subcategory == "calendar"

