import io

from vinchatbot.app.ingest.chunker import (
    ChunkingConfig,
    _calendar_event_to_text,
    chunk_document,
)
from vinchatbot.app.ingest.parsers import parse_docx
from vinchatbot.app.schemas.document import RawDocument


def test_calendar_event_chunk_leads_with_absolute_month_year():
    # Phase 1.13: the chunk must lead with the ABSOLUTE month+year (both languages) derived from the ISO
    # date, not the ambiguous "2026-2027" + "15-Jun" — that was the June-2026-returns-June-2027 bug.
    text = _calendar_event_to_text(
        {
            "event_name": "Summer final exams",
            "academic_year": "2026-2027",
            "term": "Summer",
            "date_start_iso": "2027-06-15",
            "date_end_iso": "2027-06-19",
            "date_text_original": "15-Jun",
            "event_type": "exam",
        }
    )
    assert "June 2027" in text  # absolute EN form (matches a 1.12 date-normalized query variant)
    assert "tháng 6 năm 2027" in text  # absolute VI form
    assert text.index("June 2027") < text.index("Summer final exams")  # it LEADS the chunk
    assert "2026-2027" in text  # AY label retained, just no longer the headline


def test_calendar_event_chunk_falls_back_without_iso():
    # No parseable ISO → fall back to the academic-year scope (no crash, no bogus month).
    text = _calendar_event_to_text(
        {"event_name": "Convocation ceremony", "academic_year": "2026-2027", "term": "Fall"}
    )
    assert "Convocation ceremony" in text
    assert "2026-2027" in text


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


def test_chunker_v2_builds_section_path_from_markdown_headers(monkeypatch):
    # Markdown chunking is off by default (shelved); force it on for this test.
    from types import SimpleNamespace

    from vinchatbot.app.ingest import chunker

    monkeypatch.setattr(
        chunker,
        "get_settings",
        lambda: SimpleNamespace(
            enable_markdown_parsing=True,
            chunk_max_tokens=1024,
            chunk_overlap_tokens=96,
            chunk_header_levels=2,
        ),
    )
    raw = RawDocument(
        source_url="https://policy.vinuni.edu.vn/all-policies/leave/",
        canonical_url="https://policy.vinuni.edu.vn/all-policies/leave/",
        title="Leave of Absence",
        document_type="policy_html",
        content=(
            "# Overview\n\nThis procedure covers leave of absence.\n\n"
            "## Eligibility\n\nFull-time students may apply for leave.\n\n"
            "## Procedure\n\nSubmit the leave of absence form to your advisor."
        ),
    )
    chunks = chunk_document(raw)
    paths = [c.metadata.section_path for c in chunks]
    assert ["Overview", "Eligibility"] in paths
    assert ["Overview", "Procedure"] in paths


def test_parse_docx_emits_markdown_headings_and_lists():
    docx = __import__("docx")
    document = docx.Document()
    document.add_heading("Leave of Absence", level=1)
    document.add_paragraph("Full-time students may apply.")
    document.add_paragraph("Prepare the form", style="List Bullet")
    buffer = io.BytesIO()
    document.save(buffer)

    raw = parse_docx(buffer.getvalue(), "https://policy.vinuni.edu.vn/policy.docx")

    assert raw.document_type == "markdown"
    assert "# Leave of Absence" in raw.content
    assert "Full-time students may apply." in raw.content
    assert "- Prepare the form" in raw.content

