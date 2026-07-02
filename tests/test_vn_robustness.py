from __future__ import annotations

import asyncio
import json
import uuid
from pathlib import Path

import pytest

from vinchatbot.app.agents.guardrails import (
    answer_language,
    expand_teencode,
    normalize_for_matching,
    resolve_guardrail_decision,
)
from vinchatbot.app.agents.question_scope import classify_question_scope
from vinchatbot.app.core.observability import reset_student_identity, set_student_identity

_EVAL = json.loads(
    (Path(__file__).resolve().parents[1] / "data" / "eval" / "vn_robustness.json").read_text("utf-8")
)


# --- expand_teencode unit ------------------------------------------------------------------------

@pytest.mark.parametrize(
    "raw,expected_substr",
    [
        ("hnay t co tiet j", "hom nay toi co tiet gi"),
        ("tkb cua t", "thoi khoa bieu cua toi"),
        ("t co dl nao ko", "toi co deadline nao khong"),
        ("hp 1 nam bao nhiu", "hoc phi 1 nam bao nhieu"),
        ("gpa mik bao nhiu", "gpa minh bao nhieu"),
    ],
)
def test_expand_teencode(raw, expected_substr):
    assert expand_teencode(normalize_for_matching(raw)) == expected_substr


def test_expand_teencode_leaves_clean_text_untouched():
    clean = normalize_for_matching("hôm nay tôi có tiết gì")
    assert expand_teencode(clean) == clean


# --- scope classification survives teencode/no-diacritics ----------------------------------------

@pytest.mark.parametrize(
    "message",
    [
        "hnay t có tiết j",       # hôm nay tôi có tiết gì
        "t có dl nào ko",          # tôi có deadline nào không
        "tkb của t",               # thời khóa biểu của tôi
        "gpa mik bao nhiu",        # gpa mình bao nhiêu
        "hom nay toi co tiet gi",  # no-diacritics
    ],
)
def test_teencode_personal_questions_stay_personal(message):
    # These previously fell to general_unknown → the guardrail refused a legit personal question.
    assert classify_question_scope(message, authenticated=True) == "personal_app_data"


@pytest.mark.parametrize(
    "message",
    ["hp 1 năm bao nhiu", "t có tiết j hôm nay", "tkb của mình", "hom nay toi co tiet gi"],
)
def test_teencode_questions_not_refused_by_guardrail(message):
    # The FULL guardrail (rule tier + the authenticated personal-allowance) must not refuse these for a
    # signed-in student — teencode expansion feeds both the scope allow-list and the scope classifier.
    set_student_identity(student_profile_id=uuid.uuid4(), user_id=uuid.uuid4())
    try:
        action = asyncio.run(resolve_guardrail_decision(message)).action
    finally:
        reset_student_identity()
    assert action != "out_of_scope"


# --- answer_language robustness -------------------------------------------------------------------

@pytest.mark.parametrize(
    "message",
    ["gpa mik bao nhiu", "mau don phuc khao diem", "hnay t co tiet nao ko", "vinuni co nhung nganh nao"],
)
def test_no_diacritics_teencode_detected_as_vietnamese(message):
    assert answer_language(message) == "vi"


@pytest.mark.parametrize("message", ["what is my gpa", "how many credits do i need"])
def test_english_still_detected_as_english(message):
    assert answer_language(message) == "en"


# --- over-fire guard: teencode expansion must not pull non-personal questions into personal --------

@pytest.mark.parametrize(
    "message",
    [
        "vinuni có bao nhiêu ngành",
        "học phí ngành Y là bao nhiêu",
        "thời tiết hôm nay thế nào",
        "quy định thi cuối kỳ là gì",
    ],
)
def test_teencode_expansion_no_overfire(message):
    assert classify_question_scope(message, authenticated=True) != "personal_app_data"


# --- eval set is loadable + well-formed (promoted from the investigation) --------------------------

def test_vn_robustness_eval_set_wellformed():
    cases = _EVAL["cases"]
    assert len(cases) >= 40
    assert all({"id", "kind", "clean", "q"} <= set(c) for c in cases)
