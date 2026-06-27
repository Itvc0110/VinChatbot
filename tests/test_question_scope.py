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
