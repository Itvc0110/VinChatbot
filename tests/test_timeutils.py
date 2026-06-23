from datetime import datetime

import pytest

from vinchatbot.app.core.timeutils import (
    current_academic_context,
    current_time_context,
    is_pure_time_question,
)


@pytest.mark.parametrize(
    ("date", "expected"),
    [
        # Fall boundary: Sep 1 is Fall of the year-starting AY; Aug 31 is still Summer of the prior AY.
        (datetime(2026, 9, 1), ("2026-2027", "Fall")),
        (datetime(2026, 8, 31), ("2025-2026", "Summer")),
        (datetime(2026, 12, 31), ("2026-2027", "Fall")),
        # Spring: Jan–May belongs to the AY that started the previous September.
        (datetime(2027, 1, 1), ("2026-2027", "Spring")),
        (datetime(2026, 5, 31), ("2025-2026", "Spring")),
        # Summer: Jun–Aug, same AY as the preceding Spring.
        (datetime(2026, 6, 1), ("2025-2026", "Summer")),
        # The reported live case: June 18, 2026 → Summer of AY 2025-2026.
        (datetime(2026, 6, 18), ("2025-2026", "Summer")),
    ],
)
def test_current_academic_context(date, expected):
    assert current_academic_context(date) == expected


def test_current_time_context_fields():
    ctx = current_time_context(datetime(2026, 6, 18))
    assert ctx["date"] == "2026-06-18"
    assert ctx["academic_year"] == "2025-2026"
    assert ctx["term"] == "Summer"
    assert ctx["weekday"]  # non-empty weekday name


@pytest.mark.parametrize(
    "message",
    [
        # --- Vietnamese: current term / academic year ---
        "Hiện tại tôi đang ở học kỳ nào?",
        "Học kỳ hiện tại là gì?",
        "Năm học hiện tại là năm nào?",
        "Bây giờ là năm học nào?",
        # --- Vietnamese: current date / weekday ---
        "Hôm nay là ngày bao nhiêu?",
        "Hôm nay là thứ mấy?",
        "Hôm nay thứ mấy?",
        "Bây giờ thứ mấy?",
        "Ngày mấy rồi?",
        # --- English: current term / academic year / year ---
        "What semester am I currently in?",
        "What semester am I in?",
        "which semester is it?",
        "what is the current semester",
        "what academic year are we in?",
        "what year is it?",
        # --- English: current date / weekday ---
        "what's today's date?",
        "what is the date?",
        "what day is it?",
    ],
)
def test_is_pure_time_question_positive(message):
    assert is_pure_time_question(message) is True


@pytest.mark.parametrize(
    "message",
    [
        # Calendar/data questions that need retrieval — must NOT be intercepted.
        "Kỳ thi cuối học kỳ này diễn ra khi nào?",
        "Học kỳ Fall bắt đầu ngày nào?",
        "Còn bao nhiêu tuần nữa đến hạn add/drop?",
        "When does this semester start?",
        "When are this semester's final exams?",
        "How many weeks until the add/drop deadline?",
        "Học phí học kỳ này là bao nhiêu?",
        # --- adversarial "break it" cases that broke earlier regex versions ---
        "Học kỳ nào có môn Lập trình?",          # which semester has course X (catalog data)
        "Môn Giải tích dạy vào học kỳ nào?",      # which semester is Calculus taught
        "Hôm nay là ngày khai giảng phải không?",  # is today the opening day? (calendar event)
        "Hạn nộp là ngày mấy?",                   # what date is the deadline (calendar data)
        "Kỳ thi vào ngày mấy?",                   # what date is the exam
        "what is today's assignment?",            # 'what is today' must not trigger
        "what's today's homework?",
        "what semester is the orientation in?",   # 'is the' must not match 'is it'
        "What's the current tuition for this semester?",  # 'current'+'semester' but a fee question
        "How long does the Summer term last?",
        "When is the tuition due this semester?",
        "what is the deadline date?",             # 'date' but not a today-ask
    ],
)
def test_is_pure_time_question_negative(message):
    assert is_pure_time_question(message) is False
