from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import vinchatbot.app.agents.tools as tools_mod
from vinchatbot.app.ingest.chunker import chunk_document
from vinchatbot.app.rag.retriever import RetrievedChunk
from vinchatbot.app.rag.structured_lookup import StructuredLookup
from vinchatbot.app.schemas.document import DocumentMetadata, RawDocument, stable_hash

SRC = "https://policy.vinuni.edu.vn/wp-content/uploads/2025/06/VinUni-Academic-Calendar.pdf"


def _event(name: str, etype: str, ay: str, term: str | None = None) -> dict:
    # date_start_iso/date_end_iso deliberately None so the matcher MUST re-derive dates from event_name.
    return {
        "record_id": stable_hash(f"{ay}:{name}"),
        "record_type": "calendar_event",
        "parent_doc_id": "pdoc-cal",
        "source_url": SRC,
        "title": name,
        "data": {
            "event_name": name,
            "event_type": etype,
            "academic_year": ay,
            "term": term,
            "date_start_iso": None,
            "date_end_iso": None,
            "source_url": SRC,
            "page_number": 1,
        },
        "metadata": {
            "source_url": SRC,
            "canonical_url": SRC,
            "document_title": "VinUni Academic Calendar",
            "content_hash": "hash123",
            "category": "academic",
            "subcategory": "calendar",
        },
    }


def _records() -> list[dict]:
    ay = "2026-2027"
    return [
        _event("16-20-Aug End-of-Semester Course Evaluation Period - Summer'27", "evaluation_period", ay, "Summer"),
        _event("21-31-Dec End-of-Semester Course Evaluation Period - Fall'26", "evaluation_period", ay, "Fall"),
        _event("23-27 Aug Final Exam Period - Sum'27", "exam_period", ay, "Summer"),
        _event("21-Jun-02-Jul Marking + Appeal + Grade release", "grade_release", ay, "Spring"),
        _event("25-Jan-12-Feb Marking + Appeal + Grade release", "grade_release", ay, "Fall"),
        _event("30-Aug-10-Sep Marking + Appeal + Grade release", "grade_release", ay, "Summer"),
        _event("7-18-Jun Final Exam Period - Fall'26", "exam_period", ay, "Fall"),
        _event("21-Jun Summer'27 Class Enrollment Starts (Course Registration)", "registration", ay, "Summer"),
        _event("14-Jun Summer'27 Class Timetable Release (View Mode)", "timetable_release", ay, "Summer"),
        _event("1-Oct Add/Transfer Credit/Independent Study Deadline", "add_transfer_deadline", ay, None),
        _event("26-Feb Add/Transfer Credit/Independent Study Deadline", "add_transfer_deadline", ay, None),
        _event("5-Mar Course Drop Deadline", "course_drop_deadline", ay, None),
        _event("26-Sep Convocation Day (tentatively)", "academic_event", ay, None),
        _event("21-Sep Fall'26 Instruction Begins", "instruction_begins", ay, "Fall"),
        _event("2-10-Feb Lunar New Year Holiday (tentatively)", "holiday", ay, None),
        _event("1-Jan New Year's Day holiday", "holiday", ay, None),
        _event("3-May Final Exam Schedule Release", "exam_schedule_release", ay, "Spring"),
        _event("7-Dec Final Exam Schedule Release", "exam_schedule_release", ay, "Fall"),
        _event("26-Jun Graduation Day (tentatively)", "academic_event", ay, None),
        # AY2024-2025 — for cross-AY disambiguation
        _event("20-Jun Graduation Day", "academic_event", "2024-2025", None),
        _fee_table(),
    ]


FEE_SRC = "https://policy.vinuni.edu.vn/all-policies/financial-regulations-and-tariff-for-student-2/"


def _fee_table() -> dict:
    return {
        "record_id": "fee-tuition",
        "record_type": "table_record",
        "parent_doc_id": "pdoc-fee",
        "source_url": FEE_SRC,
        "title": "Financial Regulations and Tariff (for student)",
        "data": {
            "headers": ["Column 1", "Column 2", "Column 3", "Column 4", "Column 5"],
            "rows": [
                ["Program", "Standard Duration (years)", "Listed Tuition Fee per Academic Year",
                 "Listed Tuition Fee per Semester", "Listed Tuition Fee per Credit (*)"],
                ["Bachelor of Nursing", "4", "349,650,000/year", "174,825,000/semester", "9,780,000/credit"],
                ["Doctor of Medicine", "6", "815,850,000/year", "407,925,000/ semester", "27,195,000/ credit"],
                ["Other Bachelor Programs", "4", "815,850,000/year", "407,925,000/ semester", "27,195,000/ credit"],
            ],
        },
        "metadata": {
            "source_url": FEE_SRC, "canonical_url": FEE_SRC,
            "document_title": "Financial Regulations and Tariff (for student)",
            "content_hash": "feehash", "category": "student_affairs", "subcategory": "financial",
        },
    }


def _lookup(tmp_path) -> StructuredLookup:
    path = tmp_path / "structured_records.json"
    path.write_text(json.dumps(_records(), ensure_ascii=False), encoding="utf-8")
    return StructuredLookup(str(path))


def _text(hit: dict | None) -> str:
    assert hit is not None, "expected a structured-lookup hit, got MISS"
    return hit["results"][0]["text"]


# ---- the two known grounded-but-wrong residuals -----------------------------------------------

def test_summer_evaluation_residual_en_and_vi(tmp_path):
    lookup = _lookup(tmp_path)
    for query in (
        "When is the end-of-semester course evaluation period for Summer 2027?",
        "Kỳ đánh giá môn học cuối kỳ của học kỳ Summer 2027 diễn ra khi nào?",
    ):
        text = _text(lookup.lookup(query, "calendar"))
        assert "16 tháng 8 năm 2027" in text and "20 tháng 8 năm 2027" in text
        assert "August 16, 2027" in text and "August 20, 2027" in text
        assert "23 tháng 8" not in text  # the adjacent Final-Exam-Period distractor row


def test_spring_grade_release_recovers_end_date(tmp_path):
    lookup = _lookup(tmp_path)
    text = _text(
        lookup.lookup(
            "When are Spring 2027 grades released (the marking, appeal, and grade release period)?",
            "calendar",
        )
    )
    # End date July 2 must be RE-PARSED from the event name ("21-Jun-02-Jul"); stored ISO end was None.
    assert "21 tháng 6 năm 2027" in text and "2 tháng 7 năm 2027" in text
    assert "July 2, 2027" in text
    assert "7 tháng 6 năm 2027" not in text  # the 7-18 Jun Final Exam Period distractor


# ---- collisions resolved by term / month / concept --------------------------------------------

def test_registration_not_timetable(tmp_path):
    lookup = _lookup(tmp_path)
    text = _text(lookup.lookup("When does course registration for Summer 2027 start?", "calendar"))
    assert "21 tháng 6 năm 2027" in text
    assert "14 tháng 6" not in text  # the same-month Timetable Release distractor


def test_add_transfer_deadline_term_window(tmp_path):
    lookup = _lookup(tmp_path)
    # Both Add/Transfer rows have term=None; the Spring query must pick the Feb one via term-window, not Oct.
    text = _text(
        lookup.lookup(
            "What is the Spring 2027 Add, Transfer Credit, and Independent Study deadline?", "calendar"
        )
    )
    assert "26 tháng 2 năm 2027" in text
    assert "1 tháng 10" not in text


def test_convocation_concept_and_tentative(tmp_path):
    lookup = _lookup(tmp_path)
    text = _text(lookup.lookup("When is Convocation Day in the 2026-2027 academic calendar?", "calendar"))
    assert "26 tháng 9 năm 2026" in text
    assert "dự kiến" in text and "tentatively" in text
    assert "21 tháng 9" not in text  # Instruction-Begins on 21-Sep must not win


def test_lunar_new_year_concept_en_and_vi(tmp_path):
    lookup = _lookup(tmp_path)
    for query in (
        "When is the Lunar New Year holiday in the 2026-2027 academic calendar?",
        "Kỳ nghỉ Tết Nguyên đán trong lịch năm học 2026-2027 dự kiến diễn ra khi nào?",
    ):
        text = _text(lookup.lookup(query, "calendar"))
        assert "2 tháng 2 năm 2027" in text and "10 tháng 2 năm 2027" in text
        assert "1 tháng 1" not in text  # New Year's Day (1-Jan) is the other holiday


def test_cross_ay_disambiguation(tmp_path):
    lookup = _lookup(tmp_path)
    older = _text(lookup.lookup("When is Graduation Day in the 2024-2025 calendar?", "calendar"))
    assert "20 tháng 6 năm 2025" in older and "2027" not in older
    newer = _text(lookup.lookup("When is Graduation Day in the 2026-2027 calendar?", "calendar"))
    assert "26 tháng 6 năm 2027" in newer and "2025" not in newer


# ---- misses → None (fall through to vector) ---------------------------------------------------

def test_uningested_out_of_span_year_returns_no_data(tmp_path):
    # Phase 1.19 fix: an out-of-span year is a definitive no-data refusal (empty results), not a plain
    # MISS — so vector search is skipped and the LLM can't graft a wrong-year date.
    lookup = _lookup(tmp_path)
    hit = lookup.lookup("When does Fall 2030 instruction begin?", "calendar")
    assert hit is not None and hit.get("no_data") is True and hit["results"] == []


def test_miss_ambiguous_generic_event(tmp_path):
    lookup = _lookup(tmp_path)
    # A bare academic-event query with no resolvable concept must MISS, not guess a row.
    assert lookup.lookup("What is in the 2026-2027 academic calendar?", "calendar") is None


def test_miss_fee_domain_in_stage1(tmp_path):
    lookup = _lookup(tmp_path)
    assert lookup.lookup("What is the tuition per credit?", "fee") is None


def test_miss_listing_query(tmp_path):
    lookup = _lookup(tmp_path)
    # With list_mode OFF (default) the point path has no single answer row for a listing → MISS → vector.
    assert lookup.lookup("List all Summer 2027 events and important dates", "calendar") is None


def test_calendar_list_mode_all_grade_release(tmp_path):
    lookup = _lookup(tmp_path)
    # Phase 1.27b: "all marking/grade-release periods" → enumerate every term's window (Spring/Fall/Summer),
    # deterministically from the in-memory calendar index — not a single point match.
    text = _text(
        lookup.lookup(
            "List all marking and grade release periods for the 2026-2027 academic year",
            "calendar",
            list_mode=True,
        )
    )
    assert text.count("- ") >= 3  # multi-row
    assert "Spring" in text and "Fall" in text and "Summer" in text  # every term enumerated


def test_calendar_list_mode_all_add_transfer(tmp_path):
    lookup = _lookup(tmp_path)
    # Two add/transfer deadlines in the year (1-Oct 2026, 26-Feb 2027) → both returned.
    text = _text(
        lookup.lookup("What are all the add/transfer credit deadlines in 2026-2027?", "calendar", list_mode=True)
    )
    assert "October" in text and "February" in text


def test_calendar_list_mode_gated_off_is_unchanged(tmp_path):
    lookup = _lookup(tmp_path)
    # Gated: list_mode=False (default) → a listing query stays a MISS (point-only) → vector.
    assert lookup.lookup("all marking and grade release periods for 2026-2027", "calendar") is None


def test_no_data_out_of_span_year(tmp_path):
    lookup = _lookup(tmp_path)
    # Year beyond the indexed span (index covers 2024-2027) → definitive no-data: empty results so the
    # agent refuses honestly and skips vector (which would only surface wrong-year neighbours to graft).
    for query in (
        "When does Fall 2030 instruction begin according to the academic calendar?",
        "Theo lịch học, học kỳ Fall 2030 bắt đầu giảng dạy vào ngày nào?",
    ):
        hit = lookup.lookup(query, "calendar")
        assert hit is not None and hit.get("no_data") is True and hit["results"] == []


def test_in_span_absent_year_is_miss_not_nodata(tmp_path):
    lookup = _lookup(tmp_path)
    # 2025 is WITHIN the covered span but that exact AY isn't indexed here → MISS (fall through to
    # vector), NOT a hard no-data refusal (vector might still find it).
    assert lookup.lookup("When does Fall 2025 instruction begin?", "calendar") is None


# ---- Stage 2: fee table_record (program × granularity) ----------------------------------------

def _fee_text(hit: dict | None) -> str:
    assert hit is not None, "expected a fee hit, got MISS"
    return hit["results"][0]["text"]


def test_fee_program_granularity_matrix(tmp_path):
    lookup = _lookup(tmp_path)
    cases = [
        ("What is the tuition per academic year for the Bachelor of Nursing program?", "349,650,000", "815,850,000"),
        ("What is the tuition per credit for the Bachelor of Nursing program?", "9,780,000", "27,195,000"),
        ("Học phí theo tín chỉ của chương trình Cử nhân Điều dưỡng là bao nhiêu?", "9,780,000", "27,195,000"),
        ("What is the tuition per credit for the standard Bachelor program?", "27,195,000", "9,780,000"),
        ("Học phí mỗi học kỳ của các chương trình Cử nhân khác là bao nhiêu?", "407,925,000", "349,650,000"),
        ("What is the tuition per academic year for the Doctor of Medicine program?", "815,850,000", "349,650,000"),
    ]
    for query, required, forbidden in cases:
        text = _fee_text(lookup.lookup(query, "fee"))
        assert required in text, f"{query!r} -> {text!r}"
        assert forbidden not in text, f"leaked {forbidden} in {text!r}"
        assert "VND" in text


def test_fee_currency_question(tmp_path):
    lookup = _lookup(tmp_path)
    assert "VND" in _fee_text(lookup.lookup("In what currency are VinUni tuition fees listed?", "fee"))


def test_fee_program_without_granularity_defaults_to_year(tmp_path):
    lookup = _lookup(tmp_path)
    text = _fee_text(lookup.lookup("What is the tuition for the Bachelor of Nursing program?", "fee"))
    assert "349,650,000" in text  # the per-year headline figure


def test_fee_no_program_named_is_miss(tmp_path):
    lookup = _lookup(tmp_path)
    # No program named → MISS (don't guess a default → no cross-program leakage); vector handles it.
    assert lookup.lookup("What is the tuition fee per credit?", "fee") is None


def test_fee_list_mode_all_programs_one_granularity(tmp_path):
    lookup = _lookup(tmp_path)
    # Phase 1.27a: "per-credit tuition for ALL programs" → every program's per-credit cell, and NO
    # cross-granularity leakage (no per-year / per-semester values).
    text = _fee_text(lookup.lookup("What is the per-credit tuition for all programs?", "fee", list_mode=True))
    assert "9,780,000" in text and "27,195,000" in text  # nursing + medicine/other per-credit
    assert "349,650,000" not in text and "815,850,000" not in text  # per-year must not leak
    assert "174,825,000" not in text and "407,925,000" not in text  # per-semester must not leak


def test_fee_list_mode_whole_matrix(tmp_path):
    lookup = _lookup(tmp_path)
    # No program + no granularity → the whole matrix (all programs × all granularities).
    text = _fee_text(lookup.lookup("List all tuition fees for every program", "fee", list_mode=True))
    for amount in ("349,650,000", "174,825,000", "9,780,000", "815,850,000", "407,925,000", "27,195,000"):
        assert amount in text, f"missing {amount} in {text!r}"


def test_fee_list_mode_single_cell_falls_back_to_point(tmp_path):
    lookup = _lookup(tmp_path)
    # list_mode but the query pins ONE program × ONE granularity (1×1) → point path, not enumeration.
    text = _fee_text(lookup.lookup("per-credit tuition for nursing", "fee", list_mode=True))
    assert "9,780,000" in text and "27,195,000" not in text


def test_fee_list_mode_gated_off_is_unchanged(tmp_path):
    lookup = _lookup(tmp_path)
    # Gated: list_mode=False (default) → an "all programs" query stays a MISS (no single program) → vector.
    assert lookup.lookup("per-credit tuition for all programs", "fee") is None


def test_fee_result_metadata_is_valid(tmp_path):
    lookup = _lookup(tmp_path)
    hit = lookup.lookup("tuition per credit for Bachelor of Nursing", "fee")
    assert hit is not None
    md = DocumentMetadata.model_validate(hit["results"][0]["metadata"])
    assert md.subcategory == "financial" and md.fee_type == "tuition" and md.source_url


# ---- citation contract ------------------------------------------------------------------------

def test_result_metadata_is_valid_documentmetadata(tmp_path):
    lookup = _lookup(tmp_path)
    hit = lookup.lookup("When is Convocation Day in the 2026-2027 academic calendar?", "calendar")
    assert hit is not None
    metadata = hit["results"][0]["metadata"]
    validated = DocumentMetadata.model_validate(metadata)  # must not raise → citation will render
    assert validated.source_url and validated.document_title
    assert validated.academic_year == "2026-2027"
    assert validated.event_type == "academic_event"


# ---- integration: the tools.py seam respects the flag (fail-open + parity) ---------------------

def _tool_settings(structured: bool) -> SimpleNamespace:
    return SimpleNamespace(
        enable_soft_routing=True,
        retrieval_max_k=8,
        retrieval_candidate_k=40,
        enable_structured_lookup=structured,
        enable_adaptive_retrieval=False,
        enable_query_expansion=False,
        enable_crosslingual_expansion=False,
        enable_date_normalization=False,
        enable_rerank_after_fusion=False,
        enable_reactive_expansion=False,
        reactive_expansion_min_score=0.35,
        enable_litm_reorder=True,
        enable_indirect_injection_scan=False,
    )


class _FakeRetriever:
    def __init__(self):
        raw = RawDocument(
            source_url="https://vinuni.edu.vn/cal",
            canonical_url="https://vinuni.edu.vn/cal",
            title="Cal",
            document_type="html",
            content="# Calendar\n\nSome calendar prose here for the vector path.",
        )
        self._chunks = [RetrievedChunk(text=c.text, metadata=c.metadata, score=1.0) for c in chunk_document(raw)]
        self.search_calls = 0

    async def search(self, query, filters=None, limit=8, reorder=True, boost_hints=None, expand_sections=False):
        self.search_calls += 1
        return self._chunks[:limit]


def _call_calendar_tool(monkeypatch, structured: bool, lookup_obj) -> tuple[str, _FakeRetriever]:
    retriever = _FakeRetriever()
    monkeypatch.setattr(tools_mod, "get_settings", lambda: _tool_settings(structured))
    monkeypatch.setattr(tools_mod, "get_structured_lookup", lambda settings=None: lookup_obj)
    tools = tools_mod.build_retrieval_tools(retriever)
    tool = next(t for t in tools if t.name == "search_academic_calendar")
    result = asyncio.run(tool.ainvoke({"query": "When is Convocation Day in the 2026-2027 academic calendar?"}))
    return result, retriever


def test_seam_uses_lookup_when_flag_on(monkeypatch):
    sentinel = SimpleNamespace(
        lookup=lambda query, domain, list_mode=False: {
            "results": [{"text": "STRUCTURED_HIT", "score": 1.0, "metadata": {}}]
        }
    )
    result, retriever = _call_calendar_tool(monkeypatch, structured=True, lookup_obj=sentinel)
    assert "STRUCTURED_HIT" in result
    assert retriever.search_calls == 0  # short-circuited before vector search


def test_seam_skips_lookup_when_flag_off(monkeypatch):
    def _boom(settings=None):
        raise AssertionError("structured lookup must not be consulted when the flag is off")

    monkeypatch.setattr(tools_mod, "get_settings", lambda: _tool_settings(False))
    monkeypatch.setattr(tools_mod, "get_structured_lookup", _boom)
    retriever = _FakeRetriever()
    tools = tools_mod.build_retrieval_tools(retriever)
    tool = next(t for t in tools if t.name == "search_academic_calendar")
    asyncio.run(tool.ainvoke({"query": "When is Convocation Day in the 2026-2027 academic calendar?"}))
    assert retriever.search_calls == 1  # vector path ran, lookup bypassed
