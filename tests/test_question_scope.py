from __future__ import annotations

import pytest

from vinchatbot.app.agents.question_scope import classify_question_scope


@pytest.mark.parametrize(
    "message",
    [
        "Có thông báo nào quan trọng không?",
        "Hôm nay tôi có lịch gì?",
        "Tôi có deadline nào sắp tới?",
        "Tôi đang học những môn nào?",
        "Có topic forum nào liên quan không?",
        "What is my GPA?",
        "CPA của tôi là bao nhiêu?",
        "CPA tích lũy của tôi là bao nhiêu?",
        "Do I have any tickets open?",
    ],
)
def test_personal_app_data_scope(message):
    assert classify_question_scope(message) == "personal_app_data"


@pytest.mark.parametrize(
    "message",
    [
        "Quy định rút môn là gì?",
        "Chính sách học phí thế nào?",
        "Điều kiện tốt nghiệp là gì?",
        "Quy định học bổng chính thức là gì?",
        "What is the add-drop regulation?",
    ],
)
def test_official_policy_scope(message):
    assert classify_question_scope(message) == "official_policy"


@pytest.mark.parametrize(
    "message",
    [
        "Tôi có thể rút môn CSC250 không?",
        "Deadline đăng ký môn của tôi là khi nào và quy định là gì?",
        "Tôi có đủ điều kiện học bổng này không?",
    ],
)
def test_hybrid_scope(message):
    assert classify_question_scope(message) == "hybrid"


@pytest.mark.parametrize(
    "message",
    [
        "VinUni nằm ở đâu?",
        "Xin chào",
        "",
    ],
)
def test_general_unknown_scope(message):
    assert classify_question_scope(message) == "general_unknown"


@pytest.mark.parametrize(
    "message",
    [
        "điểm CS101?",       # grade (generic) without a pronoun
        "cố vấn?",            # advisor (generic) without a pronoun
        "mã số sinh viên?",  # student id (generic) without a pronoun
        "lớp hôm nay?",      # class/session (generic) without a pronoun
        "gpa kì này?",       # inherent — personal regardless
        "cpa tích lũy?",     # inherent — personal regardless
    ],
)
def test_authenticated_student_elliptical_is_personal(message):
    # A signed-in student routinely omits the pronoun; the session scopes the answer to them.
    assert classify_question_scope(message, authenticated=True) == "personal_app_data"


@pytest.mark.parametrize(
    "message",
    [
        "điểm CS101?",
        "cố vấn?",
        "mã số sinh viên?",
        "lớp hôm nay?",
    ],
)
def test_anonymous_generic_without_pronoun_is_not_personal(message):
    # Anonymous (public assistant): a generic noun with no first-person pronoun stays non-personal
    # (precision) — only inherently-personal nouns (gpa, lịch, deadline) fire pronoun-free.
    assert classify_question_scope(message, authenticated=False) != "personal_app_data"


@pytest.mark.parametrize(
    "message",
    [
        "what courses does VinUni offer?",
        "who is the CS program director?",
        "how many credits is a typical course?",
        "what majors does VinUni offer?",
        "is the Data Science program available?",
        "who is the dean of CECS?",
        "danh sách các ngành của trường?",
        "trường có những môn nào?",
        "what programs does VinUni offer?",
    ],
)
def test_catalog_question_is_not_personal_even_authenticated(message):
    # Fix #1: a catalog / org-level question (no self-reference) is general, not personal — it must NOT
    # route to the personal specialist even for a signed-in student (it would answer with their own data).
    assert classify_question_scope(message, authenticated=True) != "personal_app_data"


@pytest.mark.parametrize(
    "message",
    [
        "gpa kì này?",
        "điểm CS101?",
        "cố vấn của tôi là ai?",
        "what's my GPA?",
        "what is my CPA?",
        "tôi còn bao nhiêu tín chỉ?",
        "lịch hôm nay của tôi?",
        "mã số sinh viên của tôi?",
        "do I have a class right now?",
        "is there a class today?",  # catalog-lookalike phrasing, but a personal schedule question
        "which courses am I eligible for?",  # self-reference "am I" keeps it personal
    ],
)
def test_personal_questions_preserved_under_catalog_guard(message):
    # The catalog guard must NOT down-route genuine personal questions (no over-correction).
    assert classify_question_scope(message, authenticated=True) == "personal_app_data"
