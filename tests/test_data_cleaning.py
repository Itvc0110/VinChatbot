from __future__ import annotations

from vinchatbot.app.ingest.chunker import _calendar_event_to_text, _fee_record_to_text
from vinchatbot.app.ingest.normalizer import strip_boilerplate


def test_calendar_event_chunk_text_includes_event_term_and_iso_date():
    text = _calendar_event_to_text(
        {
            "event_name": "9-Oct Course Drop Deadline",
            "term": "Fall",
            "academic_year": "2026-2027",
            "date_text_original": "9-Oct",
            "date_start_iso": "2026-10-09",
            "event_type": "deadline",
        }
    )
    assert text is not None
    assert "Course Drop Deadline" in text
    assert "2026-10-09" in text
    assert "Fall" in text


def test_fee_record_chunk_text_includes_amount():
    text = _fee_record_to_text(
        {
            "fee_name": "Overdue fines: For normal material",
            "fee_type": "library",
            "amount": 10000,
            "currency": "VND",
            "amount_text_original": "10,000 VND",
            "conditions": "Overdue fines: For normal material: 10,000 VND per day.",
        }
    )
    assert text is not None
    assert "10,000 VND" in text
    assert "library" in text


def test_strip_boilerplate_removes_scaffolding_and_repeated_nav():
    raw = "Policy Content\nPolicy Status\nPDF version\n# Leave of Absence\nReal body text here.\n"
    cleaned = strip_boilerplate(raw)
    assert "Policy Content" not in cleaned
    assert "PDF version" not in cleaned
    assert "# Leave of Absence" in cleaned
    assert "Real body text here." in cleaned


def test_strip_boilerplate_collapses_repeated_menu_lines():
    raw = "\n".join(["Library", "Library", "Library", "Library", "Library", "Actual content."])
    cleaned = strip_boilerplate(raw).split("\n")
    assert cleaned.count("Library") == 1
    assert "Actual content." in cleaned
