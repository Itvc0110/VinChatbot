from __future__ import annotations

import asyncio
import inspect
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from vinchatbot.app.api.routes_students import get_student_repository
from vinchatbot.app.api.routes_students import router as students_router
from vinchatbot.app.dependencies.auth import get_current_user
from vinchatbot.app.repositories.auth import AuthenticatedUser
from vinchatbot.app.repositories.students import StudentRepository

STUDENT_USER_ID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
ADMIN_USER_ID = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
PROFILE_ID = uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
INSTITUTE_ID = uuid.UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")
COURSE_ID = uuid.UUID("eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee")
NOTIFICATION_ID = uuid.UUID("33333333-3333-3333-3333-333333333333")
SECOND_NOTIFICATION_ID = uuid.UUID("33333333-3333-3333-3333-333333333334")
INVISIBLE_NOTIFICATION_ID = uuid.UUID("33333333-3333-3333-3333-333333333335")
NOW = datetime(2026, 10, 1, tzinfo=UTC)


def _run(awaitable):
    return asyncio.run(asyncio.wait_for(awaitable, timeout=2.0))


def _student_user() -> AuthenticatedUser:
    return AuthenticatedUser(
        id=STUDENT_USER_ID,
        email="student.cs.demo@vinuni.edu.vn",
        full_name="Demo CECS Student",
        preferred_name="CECS Student",
        status="active",
        roles=("student",),
    )


def _admin_user() -> AuthenticatedUser:
    return AuthenticatedUser(
        id=ADMIN_USER_ID,
        email="admin.global.demo@vinuni.edu.vn",
        full_name="Demo Global Admin",
        preferred_name="Global Admin",
        status="active",
        roles=("global_admin",),
    )


class FakeStudentRepository:
    def __init__(self):
        self.profile_ids_seen: list[uuid.UUID] = []
        self.read_notification_ids: set[uuid.UUID] = {NOTIFICATION_ID}

    async def get_current_student_profile(self, user_id):
        if user_id != STUDENT_USER_ID:
            return None
        return {
            "id": PROFILE_ID,
            "student_id": "D2026CECS001",
            "program": "Bachelor of Computer Science",
            "major": "Computer Science",
            "cohort": 2026,
            "academic_year": 1,
            "student_status": "active",
            "preferred_language": "en",
            "advisor_name": "Minh Nguyen",
            "advisor_email": "advisor.cecs.demo@vinuni.edu.vn",
            "ai_personalization_enabled": True,
            "institute": {
                "id": INSTITUTE_ID,
                "code": "CECS",
                "name_vi": "Viện Kỹ thuật và Khoa học Máy tính",
                "name_en": "College of Engineering and Computer Science",
            },
            "academic_summary": {
                "gpa": Decimal("3.40"),
                "credits_earned": 36,
                "credits_required": 120,
                "current_semester": "Fall 2026",
                "academic_status": "normal",
                "updated_at": NOW,
            },
        }

    async def get_courses(self, student_profile_id):
        self.profile_ids_seen.append(student_profile_id)
        return [
            {
                "id": COURSE_ID,
                "course_code": "CSC202",
                "course_title": "Data Structures and Algorithms",
                "credits": 3,
                "semester": "Fall 2026",
                "academic_year": "2026-2027",
                "instructor": "Tuan Nguyen",
                "institute": {
                    "id": INSTITUTE_ID,
                    "code": "CECS",
                    "name_vi": "Viện Kỹ thuật và Khoa học Máy tính",
                    "name_en": "College of Engineering and Computer Science",
                },
            }
        ]

    async def get_schedule(self, student_profile_id, *, upcoming_only=True):
        self.profile_ids_seen.append(student_profile_id)
        return [
            {
                "id": uuid.UUID("11111111-1111-1111-1111-111111111111"),
                "course_id": COURSE_ID,
                "course_code": "CSC202",
                "course_title": "Data Structures and Algorithms",
                "title": "CSC202 Lab",
                "schedule_type": "lab",
                "start_time": NOW + timedelta(days=1),
                "end_time": NOW + timedelta(days=1, hours=2),
                "location": "VinUni Campus",
                "building": "Building 2",
                "room": "201",
                "instructor": "Tuan Nguyen",
                "recurrence_rule": "FREQ=WEEKLY;COUNT=12",
            }
        ]

    async def get_deadlines(self, student_profile_id, *, upcoming_only=True):
        self.profile_ids_seen.append(student_profile_id)
        return [
            {
                "id": uuid.UUID("22222222-2222-2222-2222-222222222222"),
                "course_id": COURSE_ID,
                "course_code": "CSC202",
                "course_title": "Data Structures and Algorithms",
                "title": "CSC202 Assignment 1",
                "kind": "assignment",
                "due_at": NOW + timedelta(days=7),
                "source_title": "Demo academic seed",
                "source_url": None,
            }
        ]

    async def get_notifications(self, *, user_id, profile):
        assert user_id == STUDENT_USER_ID
        assert profile["id"] == PROFILE_ID
        return [
            {
                "id": NOTIFICATION_ID,
                "type": "academic",
                "title": "Required CECS lab safety training",
                "message": "Complete lab safety training before using CECS labs.",
                "priority": "urgent",
                "status": "published",
                "target_scope": "institute",
                "institute_id": INSTITUTE_ID,
                "institute_code": "CECS",
                "course_id": None,
                "course_code": None,
                "cohort": None,
                "deadline": NOW + timedelta(days=3),
                "event_date": None,
                "start_date": NOW - timedelta(days=1),
                "end_date": NOW + timedelta(days=3),
                "source_title": "CECS demo notice",
                "source_url": None,
                "created_at": NOW,
                "updated_at": NOW,
                "is_read": NOTIFICATION_ID in self.read_notification_ids,
                "important": True,
                "archived": False,
            },
            {
                "id": SECOND_NOTIFICATION_ID,
                "type": "deadline",
                "title": "CSC202 assignment due soon",
                "message": "Submit the next DSA assignment before the deadline.",
                "priority": "high",
                "status": "published",
                "target_scope": "course",
                "institute_id": None,
                "institute_code": None,
                "course_id": COURSE_ID,
                "course_code": "CSC202",
                "cohort": None,
                "deadline": NOW + timedelta(days=5),
                "event_date": None,
                "start_date": NOW - timedelta(days=1),
                "end_date": NOW + timedelta(days=10),
                "source_title": "CSC202 LMS",
                "source_url": None,
                "created_at": NOW,
                "updated_at": NOW,
                "is_read": SECOND_NOTIFICATION_ID in self.read_notification_ids,
                "important": False,
                "archived": False,
            }
        ]

    async def mark_notification_read(self, *, notification_id, user_id, profile):
        assert user_id == STUDENT_USER_ID
        assert profile["id"] == PROFILE_ID
        if notification_id not in {NOTIFICATION_ID, SECOND_NOTIFICATION_ID}:
            return None
        self.read_notification_ids.add(notification_id)
        return {"notification_id": notification_id, "is_read": True}

    async def mark_notification_unread(self, *, notification_id, user_id, profile):
        assert user_id == STUDENT_USER_ID
        assert profile["id"] == PROFILE_ID
        if notification_id not in {NOTIFICATION_ID, SECOND_NOTIFICATION_ID}:
            return None
        self.read_notification_ids.discard(notification_id)
        return {"notification_id": notification_id, "is_read": False}

    async def mark_all_notifications_read(self, *, user_id, profile):
        assert user_id == STUDENT_USER_ID
        assert profile["id"] == PROFILE_ID
        visible = {NOTIFICATION_ID, SECOND_NOTIFICATION_ID}
        updated_count = len(visible - self.read_notification_ids)
        self.read_notification_ids.update(visible)
        return updated_count

    async def get_suggestions(self, *, user_id, profile):
        assert user_id == STUDENT_USER_ID
        assert profile["id"] == PROFILE_ID
        base = {
            "source_id": None,
            "notification_id": None,
            "topic": "demo",
            "intent": "lookup",
            "institute_id": INSTITUTE_ID,
            "institute_code": "CECS",
            "course_id": COURSE_ID,
            "course_code": "CSC202",
            "cohort": 2026,
            "score": Decimal("8.100"),
            "priority": 3,
            "created_by_ai": True,
            "approved_by_admin": True,
            "is_active": True,
            "valid_from": NOW - timedelta(days=1),
            "valid_until": NOW + timedelta(days=30),
        }
        return [
            {
                **base,
                "id": uuid.UUID("44444444-4444-4444-4444-444444444444"),
                "question_text": "What DSA deadlines are coming up?",
                "source_type": "trend",
                "category": "trend",
                "trigger_phase": "weekly",
            },
            {
                **base,
                "id": uuid.UUID("55555555-5555-5555-5555-555555555555"),
                "question_text": "What does the lab safety notice mean for me?",
                "source_type": "notification",
                "category": "notification",
                "trigger_phase": "announcement",
            },
            {
                **base,
                "id": uuid.UUID("66666666-6666-6666-6666-666666666666"),
                "question_text": "How do I register for the CECS showcase?",
                "source_type": "manual",
                "category": "event",
                "trigger_phase": "upcoming_event",
            },
            {
                **base,
                "id": uuid.UUID("77777777-7777-7777-7777-777777777777"),
                "question_text": "When is my next CSC202 lab?",
                "source_type": "manual",
                "category": "schedule_context",
                "trigger_phase": "before_class",
            },
        ]


def _student_app(
    *,
    current_user: AuthenticatedUser | None = None,
    repository: FakeStudentRepository | None = None,
) -> FastAPI:
    app = FastAPI()
    app.include_router(students_router)

    if current_user is not None:

        async def fake_current_user():
            return current_user

        app.dependency_overrides[get_current_user] = fake_current_user

    if repository is not None:

        async def fake_student_repository():
            return repository

        app.dependency_overrides[get_student_repository] = fake_student_repository

    return app


async def _get(path: str, app: FastAPI):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.get(path)


async def _post(path: str, app: FastAPI):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.post(path)


def test_students_me_requires_auth():
    response = _run(_get("/students/me", _student_app()))

    assert response.status_code == 401


def test_student_can_get_own_profile():
    response = _run(
        _get(
            "/students/me",
            _student_app(current_user=_student_user(), repository=FakeStudentRepository()),
        )
    )

    body = response.json()
    assert response.status_code == 200
    assert body["student_id"] == "D2026CECS001"
    assert body["institute"]["code"] == "CECS"
    assert body["academic_summary"]["gpa"] == "3.40"


def test_non_student_user_is_rejected():
    response = _run(
        _get(
            "/students/me",
            _student_app(current_user=_admin_user(), repository=FakeStudentRepository()),
        )
    )

    assert response.status_code == 403


def test_courses_schedule_and_deadlines_are_scoped_to_current_student():
    repository = FakeStudentRepository()
    app = _student_app(current_user=_student_user(), repository=repository)

    courses = _run(_get("/students/me/courses", app))
    schedule = _run(_get("/students/me/schedule", app))
    deadlines = _run(_get("/students/me/deadlines", app))

    assert courses.status_code == 200
    assert schedule.status_code == 200
    assert deadlines.status_code == 200
    assert courses.json()[0]["course_code"] == "CSC202"
    assert schedule.json()[0]["course_code"] == "CSC202"
    assert deadlines.json()[0]["course_code"] == "CSC202"
    assert repository.profile_ids_seen == [PROFILE_ID, PROFILE_ID, PROFILE_ID]
    assert "OTHER" not in str([courses.json(), schedule.json(), deadlines.json()])


def test_notifications_include_read_state():
    response = _run(
        _get(
            "/students/me/notifications",
            _student_app(current_user=_student_user(), repository=FakeStudentRepository()),
        )
    )

    body = response.json()
    assert response.status_code == 200
    assert body[0]["is_read"] is True
    assert body[0]["important"] is True
    assert body[0]["archived"] is False


def test_student_notification_query_does_not_require_optional_forum_columns():
    source = inspect.getsource(StudentRepository.get_notifications)
    helper_source = inspect.getsource(StudentRepository._notification_forum_columns_available)

    assert "_notification_forum_columns_available" in source
    assert "null::uuid as forum_topic_id" in source
    assert "null::uuid as forum_comment_id" in source
    assert "information_schema.columns" in helper_source
    assert "recipient_user_id" in helper_source


def test_mark_notification_read_requires_auth():
    response = _run(
        _post(
            f"/students/me/notifications/{NOTIFICATION_ID}/read",
            _student_app(repository=FakeStudentRepository()),
        )
    )

    assert response.status_code == 401


def test_non_student_user_cannot_mark_notification_read():
    response = _run(
        _post(
            f"/students/me/notifications/{NOTIFICATION_ID}/read",
            _student_app(current_user=_admin_user(), repository=FakeStudentRepository()),
        )
    )

    assert response.status_code == 403


def test_student_can_mark_visible_notification_read():
    repository = FakeStudentRepository()
    repository.read_notification_ids.clear()
    response = _run(
        _post(
            f"/students/me/notifications/{NOTIFICATION_ID}/read",
            _student_app(current_user=_student_user(), repository=repository),
        )
    )

    body = response.json()
    assert response.status_code == 200
    assert body == {"notification_id": str(NOTIFICATION_ID), "is_read": True}
    assert NOTIFICATION_ID in repository.read_notification_ids


def test_student_can_mark_visible_notification_unread():
    repository = FakeStudentRepository()
    response = _run(
        _post(
            f"/students/me/notifications/{NOTIFICATION_ID}/unread",
            _student_app(current_user=_student_user(), repository=repository),
        )
    )

    body = response.json()
    assert response.status_code == 200
    assert body == {"notification_id": str(NOTIFICATION_ID), "is_read": False}
    assert NOTIFICATION_ID not in repository.read_notification_ids


def test_notification_read_and_unread_actions_are_idempotent():
    repository = FakeStudentRepository()
    app = _student_app(current_user=_student_user(), repository=repository)

    first_read = _run(_post(f"/students/me/notifications/{NOTIFICATION_ID}/read", app))
    second_read = _run(_post(f"/students/me/notifications/{NOTIFICATION_ID}/read", app))
    first_unread = _run(_post(f"/students/me/notifications/{NOTIFICATION_ID}/unread", app))
    second_unread = _run(_post(f"/students/me/notifications/{NOTIFICATION_ID}/unread", app))

    assert first_read.status_code == 200
    assert second_read.status_code == 200
    assert first_unread.status_code == 200
    assert second_unread.status_code == 200
    assert first_read.json() == second_read.json()
    assert first_unread.json() == second_unread.json()
    assert NOTIFICATION_ID not in repository.read_notification_ids


def test_mark_all_notifications_read_updates_visible_notifications():
    repository = FakeStudentRepository()
    app = _student_app(current_user=_student_user(), repository=repository)

    response = _run(_post("/students/me/notifications/mark-all-read", app))
    second_response = _run(_post("/students/me/notifications/mark-all-read", app))

    assert response.status_code == 200
    assert response.json() == {"updated_count": 1}
    assert second_response.status_code == 200
    assert second_response.json() == {"updated_count": 0}
    assert repository.read_notification_ids == {NOTIFICATION_ID, SECOND_NOTIFICATION_ID}


def test_student_cannot_mutate_invisible_notification():
    app = _student_app(current_user=_student_user(), repository=FakeStudentRepository())

    read_response = _run(
        _post(f"/students/me/notifications/{INVISIBLE_NOTIFICATION_ID}/read", app)
    )
    unread_response = _run(
        _post(f"/students/me/notifications/{INVISIBLE_NOTIFICATION_ID}/unread", app)
    )

    assert read_response.status_code == 404
    assert unread_response.status_code == 404


def test_suggestions_require_auth():
    response = _run(_get("/suggestions/me", _student_app(repository=FakeStudentRepository())))

    assert response.status_code == 401


def test_suggestions_are_grouped():
    response = _run(
        _get(
            "/suggestions/me",
            _student_app(current_user=_student_user(), repository=FakeStudentRepository()),
        )
    )

    body = response.json()
    assert response.status_code == 200
    assert body["trending_now"][0]["source_type"] == "trend"
    assert body["from_announcements"][0]["source_type"] == "notification"
    assert body["from_events"][0]["category"] == "event"
    assert body["for_you"][0]["category"] == "schedule_context"


def test_student_api_responses_do_not_expose_sensitive_fields():
    app = _student_app(current_user=_student_user(), repository=FakeStudentRepository())

    profile = _run(_get("/students/me", app))
    notifications = _run(_get("/students/me/notifications", app))
    suggestions = _run(_get("/suggestions/me", app))
    combined = f"{profile.json()}\n{notifications.json()}\n{suggestions.json()}"

    assert "password_hash" not in combined
    assert "token_hash" not in combined
