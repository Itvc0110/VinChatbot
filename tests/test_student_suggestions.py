from __future__ import annotations

import asyncio
import inspect
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from vinchatbot.app.repositories.students import (
    MAX_STUDENT_SUGGESTIONS,
    StudentRepository,
)

STUDENT_USER_ID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
PROFILE_ID = uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
INSTITUTE_ID = uuid.UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")
OTHER_INSTITUTE_ID = uuid.UUID("dddddddd-dddd-dddd-dddd-ddddddddddde")
COURSE_ID = uuid.UUID("eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee")
OTHER_COURSE_ID = uuid.UUID("eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeef")
NOTIFICATION_ID = uuid.UUID("33333333-3333-3333-3333-333333333333")
DEADLINE_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
SCHEDULE_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
FORUM_TOPIC_ID = uuid.UUID("44444444-4444-4444-4444-444444444444")


def _run(awaitable):
    return asyncio.run(asyncio.wait_for(awaitable, timeout=2.0))


def _profile() -> dict[str, Any]:
    return {
        "id": PROFILE_ID,
        "cohort": 2026,
        "institute": {
            "id": INSTITUTE_ID,
            "code": "CECS",
            "name_vi": "Viện Kỹ thuật và Khoa học Máy tính",
            "name_en": "College of Engineering and Computer Science",
        },
    }


def _notification(
    *,
    notification_id: uuid.UUID = NOTIFICATION_ID,
    status: str = "published",
    target_scope: str = "institute",
    institute_id: uuid.UUID | None = INSTITUTE_ID,
    course_id: uuid.UUID | None = None,
    cohort: int | None = None,
    start_delta: timedelta = timedelta(days=-1),
    end_delta: timedelta = timedelta(days=7),
    archived: bool = False,
) -> dict[str, Any]:
    now = datetime.now(UTC)
    return {
        "id": notification_id,
        "type": "deadline",
        "title": "CECS scholarship application deadline",
        "message": "Submit your scholarship application before the deadline.",
        "priority": "urgent",
        "status": status,
        "target_scope": target_scope,
        "institute_id": institute_id,
        "institute_code": "CECS",
        "course_id": course_id,
        "course_code": "CSC202" if course_id == COURSE_ID else None,
        "cohort": cohort,
        "deadline": now + timedelta(days=3),
        "event_date": None,
        "start_date": now + start_delta,
        "end_date": now + end_delta,
        "source_title": "Admin",
        "source_url": None,
        "created_at": now,
        "updated_at": now,
        "is_read": False,
        "important": True,
        "archived": archived,
    }


def _seeded_suggestion(question_text: str, *, priority: int = 30) -> dict[str, Any]:
    now = datetime.now(UTC)
    return {
        "id": uuid.uuid5(uuid.NAMESPACE_URL, question_text),
        "question_text": question_text,
        "source_type": "trend",
        "source_id": None,
        "notification_id": None,
        "topic": "trend",
        "intent": "lookup",
        "category": "trend",
        "trigger_phase": "active",
        "institute_id": INSTITUTE_ID,
        "institute_code": "CECS",
        "course_id": COURSE_ID,
        "course_code": "CSC202",
        "cohort": 2026,
        "score": Decimal(priority) / Decimal("10"),
        "priority": priority,
        "created_by_ai": True,
        "approved_by_admin": True,
        "is_active": True,
        "valid_from": now - timedelta(days=1),
        "valid_until": now + timedelta(days=30),
    }


def _repository(
    *,
    notifications: list[dict[str, Any]] | None = None,
    deadlines: list[dict[str, Any]] | None = None,
    schedule: list[dict[str, Any]] | None = None,
    seeded: list[dict[str, Any]] | None = None,
    forum_topics: list[dict[str, Any]] | None = None,
) -> StudentRepository:
    repo = StudentRepository(pool=None)  # type: ignore[arg-type]
    notification_rows = notifications or []
    deadline_rows = deadlines or []
    schedule_rows = schedule or []
    seeded_rows = seeded or []
    forum_topic_rows = forum_topics or []

    async def fetch_course_ids(student_profile_id):
        assert student_profile_id == PROFILE_ID
        return [COURSE_ID]

    async def fetch_seeded_suggestions(profile, course_ids):
        assert profile["id"] == PROFILE_ID
        assert course_ids == [COURSE_ID]
        return seeded_rows

    async def get_notifications(*, user_id, profile):
        assert user_id == STUDENT_USER_ID
        assert profile["id"] == PROFILE_ID
        return notification_rows

    async def get_deadlines(student_profile_id, *, upcoming_only=True):
        assert student_profile_id == PROFILE_ID
        assert upcoming_only is True
        return deadline_rows

    async def get_schedule(student_profile_id, *, upcoming_only=True):
        assert student_profile_id == PROFILE_ID
        assert upcoming_only is True
        return schedule_rows

    async def fetch_forum_topics(profile):
        assert profile["id"] == PROFILE_ID
        return forum_topic_rows

    repo._fetch_enrolled_course_ids = fetch_course_ids  # type: ignore[method-assign]
    repo._fetch_seeded_suggestions = fetch_seeded_suggestions  # type: ignore[method-assign]
    repo.get_notifications = get_notifications  # type: ignore[method-assign]
    repo.get_deadlines = get_deadlines  # type: ignore[method-assign]
    repo.get_schedule = get_schedule  # type: ignore[method-assign]
    repo._fetch_forum_topics_for_suggestions = fetch_forum_topics  # type: ignore[method-assign]
    return repo


def test_active_published_notification_influences_suggestions():
    repo = _repository(notifications=[_notification()])

    suggestions = _run(repo.get_suggestions(user_id=STUDENT_USER_ID, profile=_profile()))

    assert suggestions[0]["source_type"] == "notification"
    assert suggestions[0]["notification_id"] == NOTIFICATION_ID
    assert "scholarship" in suggestions[0]["question_text"].lower()


def test_hidden_notifications_do_not_influence_suggestions():
    future = _notification(
        notification_id=uuid.UUID("33333333-3333-3333-3333-333333333334"),
        status="scheduled",
        start_delta=timedelta(days=1),
    )
    draft = _notification(
        notification_id=uuid.UUID("33333333-3333-3333-3333-333333333335"),
        status="draft",
    )
    archived = _notification(
        notification_id=uuid.UUID("33333333-3333-3333-3333-333333333336"),
        status="archived",
    )
    read_archived = _notification(
        notification_id=uuid.UUID("33333333-3333-3333-3333-333333333337"),
        archived=True,
    )
    repo = _repository(notifications=[future, draft, archived, read_archived])

    suggestions = _run(repo.get_suggestions(user_id=STUDENT_USER_ID, profile=_profile()))

    assert {item["notification_id"] for item in suggestions} == {None}


def test_institute_targeting_is_respected_for_notification_suggestions():
    matching = _notification()
    nonmatching = _notification(
        notification_id=uuid.UUID("33333333-3333-3333-3333-333333333338"),
        institute_id=OTHER_INSTITUTE_ID,
    )
    repo = _repository(notifications=[nonmatching, matching])

    suggestions = _run(repo.get_suggestions(user_id=STUDENT_USER_ID, profile=_profile()))

    notification_ids = {item["notification_id"] for item in suggestions}
    assert NOTIFICATION_ID in notification_ids
    assert nonmatching["id"] not in notification_ids


def test_course_targeting_is_respected_for_notification_suggestions():
    matching = _notification(
        notification_id=uuid.UUID("33333333-3333-3333-3333-333333333339"),
        target_scope="course",
        institute_id=None,
        course_id=COURSE_ID,
    )
    nonmatching = _notification(
        notification_id=uuid.UUID("33333333-3333-3333-3333-33333333333a"),
        target_scope="course",
        institute_id=None,
        course_id=OTHER_COURSE_ID,
    )
    repo = _repository(notifications=[nonmatching, matching])

    suggestions = _run(repo.get_suggestions(user_id=STUDENT_USER_ID, profile=_profile()))

    notification_ids = {item["notification_id"] for item in suggestions}
    assert matching["id"] in notification_ids
    assert nonmatching["id"] not in notification_ids


def test_deadline_and_schedule_items_influence_suggestions():
    now = datetime.now(UTC)
    repo = _repository(
        deadlines=[
            {
                "id": DEADLINE_ID,
                "course_id": COURSE_ID,
                "course_code": "CSC202",
                "course_title": "Data Structures and Algorithms",
                "title": "CSC202 Assignment 1",
                "kind": "assignment",
                "due_at": now + timedelta(days=2),
                "source_title": "LMS",
                "source_url": None,
            }
        ],
        schedule=[
            {
                "id": SCHEDULE_ID,
                "course_id": COURSE_ID,
                "course_code": "CSC202",
                "course_title": "Data Structures and Algorithms",
                "title": "CSC202 Lab",
                "schedule_type": "lab",
                "start_time": now + timedelta(days=1),
                "end_time": now + timedelta(days=1, hours=2),
            }
        ],
    )

    suggestions = _run(repo.get_suggestions(user_id=STUDENT_USER_ID, profile=_profile()))

    source_types = {item["source_type"] for item in suggestions}
    assert "deadline" in source_types
    assert "schedule" in source_types


def test_visible_forum_topics_influence_suggestions():
    now = datetime.now(UTC)
    repo = _repository(
        forum_topics=[
            {
                "id": FORUM_TOPIC_ID,
                "title": "Final exam preparation tips",
                "content": "Share what to review before finals.",
                "tags": ["exam"],
                "is_pinned": True,
                "deleted": False,
                "created_at": now - timedelta(days=1),
                "last_activity_at": now,
                "category_slug": "academic-qa",
            }
        ]
    )

    suggestions = _run(repo.get_suggestions(user_id=STUDENT_USER_ID, profile=_profile()))

    forum_suggestions = [
        item for item in suggestions if item["source_type"] == "forum_topic"
    ]
    assert forum_suggestions
    assert forum_suggestions[0]["source_id"] == FORUM_TOPIC_ID
    assert forum_suggestions[0]["question_text"] == "What should I prepare for upcoming exams?"


def test_hidden_forum_topics_do_not_influence_suggestions():
    repo = _repository(
        forum_topics=[
            {
                "id": FORUM_TOPIC_ID,
                "title": "Archived scholarship Q&A",
                "content": "Scholarship discussion",
                "tags": ["scholarship"],
                "is_pinned": True,
                "deleted": True,
                "created_at": datetime.now(UTC) - timedelta(days=1),
                "last_activity_at": datetime.now(UTC),
                "category_slug": "scholarships-opportunities",
            }
        ]
    )

    suggestions = _run(repo.get_suggestions(user_id=STUDENT_USER_ID, profile=_profile()))

    assert "forum_topic" not in {item["source_type"] for item in suggestions}


def test_forum_topic_suggestion_fetch_filters_archived_and_cross_institute_topics():
    source = inspect.getsource(StudentRepository._fetch_forum_topics_for_suggestions)

    assert "t.deleted = false" in source
    assert "cat.is_active = true" in source
    assert "author_profile.institute_id = %s" in source


def test_suggestions_are_deduplicated_limited_and_shape_stable():
    repeated_question = "What deadlines should I focus on next?"
    seeded = [_seeded_suggestion(repeated_question, priority=priority) for priority in range(20)]
    repo = _repository(seeded=seeded)

    suggestions = _run(repo.get_suggestions(user_id=STUDENT_USER_ID, profile=_profile()))

    assert len(suggestions) <= MAX_STUDENT_SUGGESTIONS
    assert [item["question_text"] for item in suggestions].count(repeated_question) == 1
    first = suggestions[0]
    assert {
        "id",
        "question_text",
        "source_type",
        "source_id",
        "notification_id",
        "topic",
        "intent",
        "category",
        "trigger_phase",
        "institute_id",
        "institute_code",
        "course_id",
        "course_code",
        "cohort",
        "score",
        "priority",
        "created_by_ai",
        "approved_by_admin",
        "is_active",
        "valid_from",
        "valid_until",
    } <= set(first)
