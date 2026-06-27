from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from vinchatbot.app.api.routes_personalization import (
    get_personalization_repository,
)
from vinchatbot.app.api.routes_personalization import (
    router as personalization_router,
)
from vinchatbot.app.dependencies.auth import get_current_user
from vinchatbot.app.repositories.auth import AuthenticatedUser
from vinchatbot.app.repositories.personalization import (
    MAX_CONTEXT_COURSES,
    PersonalizationRepository,
    build_personalization_prompt,
)
from vinchatbot.app.schemas.personalization import (
    PersonalizationAcademicSummary,
    PersonalizationContext,
    PersonalizationConversation,
    PersonalizationCourse,
    PersonalizationDeadline,
    PersonalizationForumTopic,
    PersonalizationInstitute,
    PersonalizationNotification,
    PersonalizationScheduleItem,
    PersonalizationStudentProfile,
    PersonalizationSuggestion,
)

STUDENT_USER_ID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
ADMIN_USER_ID = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
OTHER_USER_ID = uuid.UUID("99999999-9999-9999-9999-999999999999")
PROFILE_ID = uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
INSTITUTE_ID = uuid.UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")
COURSE_ID = uuid.UUID("eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee")
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


def sample_context(*, ai_enabled: bool = True) -> PersonalizationContext:
    return PersonalizationContext(
        profile=PersonalizationStudentProfile(
            id=PROFILE_ID,
            student_id="D2026CECS001",
            program="Bachelor of Computer Science",
            major="Computer Science",
            cohort=2026,
            academic_year=1,
            preferred_language="en",
            ai_personalization_enabled=ai_enabled,
            institute=PersonalizationInstitute(
                id=INSTITUTE_ID,
                code="CECS",
                name_vi="Viện Kỹ thuật và Khoa học Máy tính",
                name_en="College of Engineering and Computer Science",
            ),
            academic_summary=PersonalizationAcademicSummary(
                gpa=Decimal("3.40"),
                credits_earned=36,
                credits_required=120,
                current_semester="Fall 2026",
                academic_status="normal",
            ),
        ),
        courses=[
            PersonalizationCourse(
                id=COURSE_ID,
                course_code="CSC202",
                course_title="Data Structures and Algorithms",
                semester="Fall 2026",
                academic_year="2026-2027",
                instructor="Tuan Nguyen",
            )
        ],
        schedule=[
            PersonalizationScheduleItem(
                id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
                title="CSC202 Lab",
                schedule_type="lab",
                start_time=NOW + timedelta(days=1),
                end_time=NOW + timedelta(days=1, hours=2),
                course_code="CSC202",
                course_title="Data Structures and Algorithms",
                location="VinUni Campus",
                room="201",
            )
        ],
        deadlines=[
            PersonalizationDeadline(
                id=uuid.UUID("22222222-2222-2222-2222-222222222222"),
                title="CSC202 Assignment 1",
                due_at=NOW + timedelta(days=7),
                kind="assignment",
                course_code="CSC202",
                course_title="Data Structures and Algorithms",
            )
        ],
        notifications=[
            PersonalizationNotification(
                id=uuid.UUID("33333333-3333-3333-3333-333333333333"),
                type="academic",
                title="Required CECS lab safety training",
                priority="urgent",
                deadline=NOW + timedelta(days=3),
                source_title="CECS demo notice",
            )
        ],
        suggestions=[
            PersonalizationSuggestion(
                id=uuid.UUID("44444444-4444-4444-4444-444444444444"),
                question_text="What DSA deadlines are coming up?",
                source_type="trend",
                category="trend",
                priority=3,
            )
        ],
        forum_topics=[
            PersonalizationForumTopic(
                id=uuid.UUID("55555555-5555-5555-5555-555555555555"),
                title="Tips for the DSA midterm",
                category_slug="academics",
                category_name_en="Academics",
                is_pinned=True,
                last_activity_at=NOW,
            )
        ],
        recent_conversations=[
            PersonalizationConversation(
                id=uuid.UUID("66666666-6666-6666-6666-666666666666"),
                title="When is add/drop?",
                topic="academic",
                updated_at=NOW,
                last_message_at=NOW,
            )
        ],
    )


class FakePersonalizationRepository:
    def __init__(self, context: PersonalizationContext | None) -> None:
        self.context = context
        self.requested_user_ids: list[uuid.UUID] = []

    async def get_context(self, user_id: uuid.UUID) -> PersonalizationContext | None:
        self.requested_user_ids.append(user_id)
        # Backend-owned context is scoped to the requesting user: a non-matching id never
        # resolves to another student's data.
        if user_id != STUDENT_USER_ID:
            return None
        return self.context


def _app(
    *,
    current_user: AuthenticatedUser | None = None,
    repository: FakePersonalizationRepository | None = None,
) -> FastAPI:
    app = FastAPI()
    app.include_router(personalization_router)

    if current_user is not None:

        async def fake_current_user():
            return current_user

        app.dependency_overrides[get_current_user] = fake_current_user

    if repository is not None:

        async def fake_repository():
            return repository

        app.dependency_overrides[get_personalization_repository] = fake_repository

    return app


async def _get(path: str, app: FastAPI):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.get(path)


# --- Endpoint behaviour ----------------------------------------------------


def test_anonymous_personalization_context_is_blocked():
    response = _run(
        _get(
            "/personalization/me/context",
            _app(repository=FakePersonalizationRepository(sample_context())),
        )
    )

    assert response.status_code == 401


def test_admin_does_not_receive_student_context():
    repository = FakePersonalizationRepository(sample_context())
    response = _run(
        _get(
            "/personalization/me/context",
            _app(current_user=_admin_user(), repository=repository),
        )
    )

    assert response.status_code == 403
    # The student-only guard rejects before the repository is ever consulted.
    assert repository.requested_user_ids == []


def test_student_gets_only_their_own_bounded_context():
    repository = FakePersonalizationRepository(sample_context())
    response = _run(
        _get(
            "/personalization/me/context",
            _app(current_user=_student_user(), repository=repository),
        )
    )

    body = response.json()
    assert response.status_code == 200
    # Context was fetched for THIS student's id only.
    assert repository.requested_user_ids == [STUDENT_USER_ID]
    assert body["profile"]["student_id"] == "D2026CECS001"
    assert body["profile"]["institute"]["code"] == "CECS"
    assert body["courses"][0]["course_code"] == "CSC202"
    assert body["schedule"][0]["course_code"] == "CSC202"
    assert body["deadlines"][0]["title"] == "CSC202 Assignment 1"
    assert body["notifications"][0]["title"] == "Required CECS lab safety training"
    assert body["suggestions"][0]["question_text"] == "What DSA deadlines are coming up?"
    assert body["forum_topics"][0]["title"] == "Tips for the DSA midterm"
    assert body["recent_conversations"][0]["title"] == "When is add/drop?"


def test_student_without_profile_gets_404():
    repository = FakePersonalizationRepository(None)
    response = _run(
        _get(
            "/personalization/me/context",
            _app(current_user=_student_user(), repository=repository),
        )
    )

    assert response.status_code == 404


# --- Prompt rendering ------------------------------------------------------


def test_prompt_is_bounded_and_includes_each_source():
    prompt = build_personalization_prompt(sample_context())

    assert "Student profile:" in prompt
    assert "CSC202" in prompt
    assert "CSC202 Assignment 1" in prompt
    assert "Required CECS lab safety training" in prompt
    assert "What DSA deadlines are coming up?" in prompt
    assert "Tips for the DSA midterm" in prompt
    assert "When is add/drop?" in prompt
    assert len(prompt) <= 6000


# --- Repository scoping / exclusions ---------------------------------------


class FakeStudentRepository:
    """Minimal stand-in for StudentRepository that records the ids it is queried with."""

    def __init__(self) -> None:
        self.profile_ids_seen: list[uuid.UUID] = []
        self.notification_user_ids: list[uuid.UUID] = []
        self.suggestion_user_ids: list[uuid.UUID] = []

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
        # More than the bound so truncation is observable.
        return [
            {
                "id": uuid.uuid5(uuid.NAMESPACE_URL, f"course-{index}"),
                "course_code": f"CSC{200 + index}",
                "course_title": f"Course {index}",
                "credits": 3,
                "semester": "Fall 2026",
                "academic_year": "2026-2027",
                "instructor": "Tuan Nguyen",
                "institute": None,
            }
            for index in range(MAX_CONTEXT_COURSES + 2)
        ]

    async def get_schedule(self, student_profile_id, *, upcoming_only=True):
        self.profile_ids_seen.append(student_profile_id)
        assert upcoming_only is True
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
                "recurrence_rule": None,
            }
        ]

    async def get_deadlines(self, student_profile_id, *, upcoming_only=True):
        self.profile_ids_seen.append(student_profile_id)
        assert upcoming_only is True
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
        self.notification_user_ids.append(user_id)
        assert profile["id"] == PROFILE_ID
        return [
            {
                "id": uuid.UUID("33333333-3333-3333-3333-333333333333"),
                "type": "academic",
                "title": "Visible lab safety training",
                "message": "Complete lab safety training.",
                "priority": "urgent",
                "status": "published",
                "target_scope": "institute",
                "institute_id": INSTITUTE_ID,
                "course_id": None,
                "cohort": None,
                "deadline": NOW + timedelta(days=3),
                "event_date": None,
                "start_date": NOW - timedelta(days=1),
                "end_date": NOW + timedelta(days=3),
                "source_title": "CECS demo notice",
                "source_url": None,
                "created_at": NOW,
                "updated_at": NOW,
                "is_read": False,
                "important": True,
                "archived": False,
            },
            {
                "id": uuid.UUID("33333333-3333-3333-3333-3333333333aa"),
                "type": "academic",
                "title": "Archived stale notice",
                "message": "This was archived by the student.",
                "priority": "high",
                "status": "published",
                "target_scope": "institute",
                "institute_id": INSTITUTE_ID,
                "course_id": None,
                "cohort": None,
                "deadline": None,
                "event_date": None,
                "start_date": NOW - timedelta(days=10),
                "end_date": NOW + timedelta(days=10),
                "source_title": "Old notice",
                "source_url": None,
                "created_at": NOW,
                "updated_at": NOW,
                "is_read": True,
                "important": False,
                "archived": True,
            },
        ]

    async def get_suggestions(self, *, user_id, profile):
        self.suggestion_user_ids.append(user_id)
        assert profile["id"] == PROFILE_ID
        return [
            {
                "id": uuid.UUID("44444444-4444-4444-4444-444444444444"),
                "question_text": "What DSA deadlines are coming up?",
                "source_type": "trend",
                "category": "trend",
                "priority": 3,
            }
        ]


def _repository_with_fake_students() -> tuple[PersonalizationRepository, FakeStudentRepository]:
    repository = PersonalizationRepository(pool=None)  # type: ignore[arg-type]
    fake_students = FakeStudentRepository()
    repository.students = fake_students  # type: ignore[assignment]

    async def fake_forum_topics(profile):
        assert profile["id"] == PROFILE_ID
        return [
            {
                "id": uuid.UUID("55555555-5555-5555-5555-555555555555"),
                "title": "Tips for the DSA midterm",
                "category_slug": "academics",
                "category_name_en": "Academics",
                "is_pinned": True,
                "last_activity_at": NOW,
            }
        ]

    async def fake_recent_conversations(user_id):
        assert user_id == STUDENT_USER_ID
        return [
            {
                "id": uuid.UUID("66666666-6666-6666-6666-666666666666"),
                "title": "When is add/drop?",
                "topic": "academic",
                "updated_at": NOW,
                "last_message_at": NOW,
            }
        ]

    repository._fetch_forum_topics = fake_forum_topics  # type: ignore[assignment]
    repository._fetch_recent_conversations = fake_recent_conversations  # type: ignore[assignment]
    return repository, fake_students


def test_repository_returns_none_for_user_without_profile():
    repository, _ = _repository_with_fake_students()
    assert _run(repository.get_context(OTHER_USER_ID)) is None


def test_repository_scopes_every_source_to_the_current_student():
    repository, fake_students = _repository_with_fake_students()

    context = _run(repository.get_context(STUDENT_USER_ID))

    assert context is not None
    # Courses/schedule/deadlines are all fetched with THIS student's profile id only.
    assert set(fake_students.profile_ids_seen) == {PROFILE_ID}
    # Notifications + suggestions are fetched for THIS user id only.
    assert fake_students.notification_user_ids == [STUDENT_USER_ID]
    assert fake_students.suggestion_user_ids == [STUDENT_USER_ID]


def test_repository_applies_per_source_limits():
    repository, _ = _repository_with_fake_students()

    context = _run(repository.get_context(STUDENT_USER_ID))

    assert context is not None
    assert len(context.courses) == MAX_CONTEXT_COURSES


def test_repository_excludes_archived_notifications():
    repository, _ = _repository_with_fake_students()

    context = _run(repository.get_context(STUDENT_USER_ID))

    assert context is not None
    titles = [notification.title for notification in context.notifications]
    assert "Visible lab safety training" in titles
    assert "Archived stale notice" not in titles
