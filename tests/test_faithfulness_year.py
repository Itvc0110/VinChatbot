from __future__ import annotations

from vinchatbot.app.agents.guardrails import assess_faithfulness

# Evidence is a retrieved Fall'26 instruction-begins chunk (the real source of the observed graft).
_EVIDENCE = [
    "Academic calendar event — September 2026 (tháng 9 năm 2026): 21-Sep Fall'26 Instruction Begins. "
    "Term/Học kỳ: Fall 2026-2027. Date: 21-Sep (2026-09-21)."
]


def test_grafted_year_is_unfaithful_en():
    # The day "21" IS in the evidence, but the year 2030 is fabricated → must be caught now.
    assert assess_faithfulness("Fall 2030 instruction begins on September 21, 2030.", _EVIDENCE) is False


def test_grafted_year_is_unfaithful_vi():
    assert assess_faithfulness(
        "Học kỳ Fall 2030 bắt đầu giảng dạy vào ngày 21 tháng 9 năm 2030.", _EVIDENCE
    ) is False


def test_correct_year_is_faithful():
    assert assess_faithfulness("Fall 2026 instruction begins on September 21, 2026.", _EVIDENCE) is True


def test_year_in_evidence_range_form_is_faithful():
    # Answer asserts 2026 and 2027; both appear (in "2026-2027") → grounded.
    assert assess_faithfulness("This is for academic year 2026-2027.", _EVIDENCE) is True


def test_non_year_numeric_overlap_unchanged():
    # No year asserted → existing lenient any-number-overlap behaviour preserved.
    assert assess_faithfulness("The library overdue fine is 10,000 VND per day.", ["... 10000 VND ..."]) is True


def test_no_numeric_facts_is_faithful():
    assert assess_faithfulness("Please contact the registrar for details.", _EVIDENCE) is True


def test_no_evidence_is_faithful():
    # No retrieved evidence → faithfulness is a no-op (citation-presence guard covers it).
    assert assess_faithfulness("Anything at all in 2030.", []) is True
