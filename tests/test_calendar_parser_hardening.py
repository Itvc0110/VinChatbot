"""Phase 1.13 — crawler/parser hardening for calendar correctness.

Covers the three audited bugs that let "June 2026 → June 2027" recur at full scale:
  1. infer_academic_year mislabeling (first incidental year-range / coin-flip fallback).
  2. extract_calendar_events keyword gate too narrow (dropped evaluation/commencement/VN holidays).
  3. _date_token_to_iso hardcoding 2025/2026 when no academic year is known.
"""

from vinchatbot.app.ingest.parsers import (
    _term_from_month,
    extract_calendar_events,
    infer_academic_year,
    infer_event_type,
    normalize_date_range,
)
from vinchatbot.app.schemas.document import RawDocument

# --- Fix 1: infer_academic_year ---

def test_ay_prefers_title_span_over_incidental_range():
    # A copyright/footer range appears first, but the real AY sits next to the calendar title.
    text = "© 2020-2025 VinUniversity. All rights reserved.\n2026 - 2027 ACADEMIC CALENDAR\n..."
    assert infer_academic_year(text, "https://policy.vinuni.edu.vn/calendar.pdf") == "2026-2027"


def test_ay_ignores_non_consecutive_range():
    # '2020-2025' is not an academic year (5-year span) → must not be returned.
    assert infer_academic_year("Established 2020-2025 across campuses.", "https://x/y.pdf") is None


def test_ay_from_url_short_form_when_text_silent():
    text = "VinUni Academic Calendar\nInstruction begins in September."
    url = "https://vinuni.edu.vn/wp-content/uploads/2020/07/VinUni-Academic-Calendar_AY24-25_vF.pdf"
    assert infer_academic_year(text, url) == "2024-2025"


def test_ay_from_url_bare_short_form():
    url = "https://vinuni.edu.vn/wp-content/uploads/2022/08/VinUni-AcademicCalendar22-23.pdf"
    assert infer_academic_year("Academic Calendar", url) == "2022-2023"


def test_ay_no_coinflip_fallback():
    # Both 2025 and 2026 appear but never as a consecutive range → the old code returned
    # "2025-2026"; the hardened code must return None (no guessing).
    text = "Tuition for 2025 cohort. A note about 2026 enrollment elsewhere."
    assert infer_academic_year(text, "https://x/y.pdf") is None


def test_ay_upload_path_year_not_mistaken_for_ay():
    # The '/2025/06/' upload directory must NOT become the academic year for an AY2026-27 PDF.
    text = "2026 - 2027 ACADEMIC CALENDAR\nFall 2026 Instruction Begins 8 September."
    url = "https://policy.vinuni.edu.vn/wp-content/uploads/2025/06/VinUni-Academic-Calendar.pdf"
    assert infer_academic_year(text, url) == "2026-2027"


# --- Fix 2: broadened calendar-event keyword gate ---

def _calendar_raw(content: str, academic_year: str = "2026-2027") -> RawDocument:
    return RawDocument(
        source_url="https://policy.vinuni.edu.vn/calendar.pdf",
        canonical_url="https://policy.vinuni.edu.vn/calendar.pdf",
        title="Academic Calendar",
        document_type="pdf",
        content=content,
        metadata={"academic_year": academic_year},
    )


def test_evaluation_and_commencement_now_captured():
    raw = _calendar_raw(
        "# Trang 1\n\n"
        "Course Evaluation Period 16-20 Aug\n"
        "Commencement Ceremony 30 Aug\n"
        "Orientation Week 1-5 Sep\n"
    )
    names = [e.event_name for e in extract_calendar_events(raw)]
    assert any("Evaluation" in n for n in names)
    assert any("Commencement" in n for n in names)
    assert any("Orientation" in n for n in names)


def test_vietnamese_holiday_captured():
    raw = _calendar_raw("# Trang 1\n\nGiỗ Tổ Hùng Vương 16-Apr\nQuốc Khánh 2-Sep\n")
    names = [e.event_name for e in extract_calendar_events(raw)]
    assert any("Hùng Vương" in n for n in names)


def test_noise_line_without_keyword_still_excluded():
    # A dated line with no calendar concept (e.g. a footer revision stamp) is not an event.
    raw = _calendar_raw("# Trang 1\n\nDocument last revised 12 Mar 2024 by the office\n")
    assert extract_calendar_events(raw) == []


def test_phase131_holidays_now_captured():
    # Phase 1.31: the authoritative calendar PDF lists these one-per-line with no keyword the old gate
    # matched ("Victory Day"/"Labor Day"/"Vietnam Culture Day"/"Independent Study Week"), so they were
    # dropped from the structured index → date lookups (e.g. calendar-victory-day-vi) hedged. The gate now
    # carries these holiday/period keywords.
    raw = _calendar_raw(
        "# Trang 1\n\n"
        "30-Apr Victory Day\n"
        "1-May Labor Day\n"
        "24-Nov Vietnam Culture Day (tentatively)\n"
        "4-8-Jan Independent Study Week\n"
    )
    names = [e.event_name for e in extract_calendar_events(raw)]
    assert any("Victory Day" in n for n in names)
    assert any("Labor Day" in n for n in names)
    assert any("Vietnam Culture Day" in n for n in names)
    assert any("Independent Study Week" in n for n in names)


def test_version_stamp_line_still_excluded():
    # The calendar PDF's "Version: 5/25/2026" line must NOT become an event (no event keyword added for it).
    raw = _calendar_raw("# Trang 1\n\nVersion: 5/25/2026\n")
    assert extract_calendar_events(raw) == []


# --- Fix 3: no hardcoded year when academic year is unknown ---

def test_no_year_context_returns_none_not_guess():
    # No academic-year bounds, no year in the token → must not invent 2025/2026.
    start, end = normalize_date_range("15-Jun", academic_year=None)
    assert start is None and end is None


def test_year_context_resolves_correctly():
    # With AY2026-2027, June (month < 9) resolves to the END year 2027 (Sep→Aug boundary).
    start, _ = normalize_date_range("15-Jun", academic_year="2026-2027")
    assert start == "2027-06-15"


# --- Phase 1.13b: end-of-term event-type distinction + term inference ---

def test_end_of_term_event_types_are_distinct():
    assert infer_event_type("Final Exam Schedule Release") == "exam_schedule_release"
    assert infer_event_type("End-of-Semester Course Evaluation Period") == "evaluation_period"
    assert infer_event_type("Marking + Appeal + Grade release") == "grade_release"
    assert infer_event_type("11-22-Jan Final Exam Period - Fall'26") == "exam_period"


def test_term_from_month_maps_end_of_term_periods():
    assert _term_from_month("2027-01-25") == "Fall"    # Jan grade-release → Fall
    assert _term_from_month("2027-06-21") == "Spring"   # Jun grade-release → Spring
    assert _term_from_month("2027-08-30") == "Summer"   # Aug grade-release → Summer
    assert _term_from_month("2027-03-10") is None       # ambiguous month → no guess


def test_grade_release_gets_inferred_term_but_labelled_exam_keeps_source():
    raw = _calendar_raw(
        "# Trang 1\n\n"
        "21-Jun-02-Jul Marking + Appeal + Grade release\n"          # no term label → infer Spring
        "7-18-Jun Final Exam Period - Fall'26\n"                    # explicit Fall label → keep it
    )
    by_name = {e.event_name: e for e in extract_calendar_events(raw)}
    grade = next(e for n, e in by_name.items() if "Grade release" in n)
    examp = next(e for n, e in by_name.items() if "Final Exam Period" in n)
    assert grade.term == "Spring"   # inferred from June start month
    assert examp.term == "Fall"     # source label preserved (drives the source-inconsistency case)
