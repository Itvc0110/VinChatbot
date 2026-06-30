from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from vinchatbot.app.api.routes_admin_notifications import (
    get_admin_notification_repository,
)
from vinchatbot.app.api.routes_admin_notifications import router as admin_notifications_router
from vinchatbot.app.api.routes_students import get_student_repository
from vinchatbot.app.api.routes_students import router as students_router
from vinchatbot.app.dependencies.auth import get_current_user
from vinchatbot.app.repositories.admin_notifications import NotificationPermissionError
from vinchatbot.app.repositories.auth import AuthenticatedUser

GLOBAL_ADMIN_ID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
CECS_ADMIN_ID = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
STUDENT_ID = uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
OTHER_STUDENT_ID = uuid.UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")
PROFILE_ID = uuid.UUID("eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee")
OTHER_PROFILE_ID = uuid.UUID("ffffffff-ffff-ffff-ffff-ffffffffffff")
CECS_INSTITUTE_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
VIB_INSTITUTE_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
NOW = datetime(2026, 6, 27, 8, 0, tzinfo=UTC)


def _run(awaitable):
    return asyncio.run(asyncio.wait_for(awaitable, timeout=2.0))


def _global_admin() -> AuthenticatedUser:
    return AuthenticatedUser(
        id=GLOBAL_ADMIN_ID,
        email="admin.global.demo@vinuni.edu.vn",
        full_name="Global Admin",
        preferred_name=None,
        status="active",
        roles=("global_admin",),
    )


def _cecs_admin() -> AuthenticatedUser:
    return AuthenticatedUser(
        id=CECS_ADMIN_ID,
        email="admin.cecs.demo@vinuni.edu.vn",
        full_name="CECS Admin",
        preferred_name=None,
        status="active",
        roles=("institute_admin",),
    )


def _student(user_id: uuid.UUID = STUDENT_ID) -> AuthenticatedUser:
    return AuthenticatedUser(
        id=user_id,
        email="student.cs.demo@vinuni.edu.vn",
        full_name="Student",
        preferred_name=None,
        status="active",
        roles=("student",),
    )


class NotificationStore:
    def __init__(self):
        self.rows: dict[uuid.UUID, dict[str, Any]] = {}

    def make_row(self, payload: dict[str, Any], created_by: uuid.UUID) -> dict[str, Any]:
        notification_id = uuid.uuid4()
        now = NOW
        row = {
            "id": notification_id,
            "type": payload.get("type", "academic"),
            "title": payload["title"],
            "message": payload["message"],
            "priority": payload.get("priority", "medium"),
            "status": payload.get("status", "draft"),
            "target_scope": payload.get("target_scope", "all"),
            "institute_id": payload.get("institute_id"),
            "institute_code": "CECS" if payload.get("institute_id") == CECS_INSTITUTE_ID else None,
            "course_id": None,
            "course_code": None,
            "cohort": payload.get("cohort"),
            "deadline": payload.get("deadline"),
            "event_date": payload.get("event_date"),
            "start_date": payload.get("start_date"),
            "end_date": payload.get("end_date"),
            "source_title": payload.get("source_title"),
            "source_url": payload.get("source_url"),
            "forum_topic_id": payload.get("forum_topic_id"),
            "forum_comment_id": payload.get("forum_comment_id"),
            "created_by": created_by,
            "created_by_email": "admin.global.demo@vinuni.edu.vn",
            "created_by_name": "Global Admin",
            "created_at": now,
            "updated_at": now,
            "is_read": False,
            "important": False,
            "archived": False,
        }
        self.rows[notification_id] = row
        return row


class FakeAdminNotificationRepository:
    def __init__(self, store: NotificationStore):
        self.store = store

    async def list_notifications(self, current_user):
        scope = self._scope(current_user)
        rows = list(self.store.rows.values())
        if scope is None:
            return rows
        return [
            row
            for row in rows
            if row["target_scope"] == "institute" and row["institute_id"] == scope
        ]

    async def list_target_institutes(self, current_user):
        scope = self._scope(current_user)
        targets = [
            {
                "id": CECS_INSTITUTE_ID,
                "code": "CECS",
                "name_vi": "CECS",
                "name_en": "CECS",
            },
            {
                "id": VIB_INSTITUTE_ID,
                "code": "VIB",
                "name_vi": "VIB",
                "name_en": "VIB",
            },
        ]
        if scope is None:
            return targets
        return [target for target in targets if target["id"] == scope]

    async def get_notification(self, *, notification_id, current_user):
        row = self.store.rows.get(notification_id)
        if row is None:
            return None
        scope = self._scope(current_user)
        if scope is not None and row["institute_id"] != scope:
            return None
        return row

    async def create_notification(self, *, current_user, request):
        self._ensure_scope(current_user, request.target_scope, request.institute_id)
        return self.store.make_row(request.model_dump(), current_user.id)

    async def update_notification(self, *, notification_id, current_user, request):
        row = await self.get_notification(
            notification_id=notification_id,
            current_user=current_user,
        )
        if row is None:
            return None
        payload = request.model_dump(exclude_unset=True)
        target_scope = payload.get("target_scope", row["target_scope"])
        institute_id = payload.get("institute_id", row["institute_id"])
        self._ensure_scope(current_user, target_scope, institute_id)
        row.update(payload)
        row["updated_at"] = NOW
        return row

    async def publish_notification(self, *, notification_id, current_user):
        row = await self.get_notification(
            notification_id=notification_id,
            current_user=current_user,
        )
        if row is None:
            return None
        row["status"] = "published"
        row["start_date"] = NOW
        row["updated_at"] = NOW
        return row

    async def schedule_notification(self, *, notification_id, current_user, request):
        row = await self.get_notification(
            notification_id=notification_id,
            current_user=current_user,
        )
        if row is None:
            return None
        row["status"] = "scheduled"
        row["start_date"] = request.publish_at
        row["end_date"] = request.end_date
        row["updated_at"] = NOW
        return row

    async def archive_notification(self, *, notification_id, current_user):
        row = await self.get_notification(
            notification_id=notification_id,
            current_user=current_user,
        )
        if row is None:
            return None
        row["status"] = "archived"
        row["updated_at"] = NOW
        return row

    def _scope(self, current_user):
        if "global_admin" in current_user.roles:
            return None
        if "institute_admin" in current_user.roles or "staff" in current_user.roles:
            return CECS_INSTITUTE_ID
        return object()

    def _ensure_scope(self, current_user, target_scope, institute_id):
        scope = self._scope(current_user)
        if scope is None:
            return
        if target_scope != "institute" or institute_id != scope:
            raise NotificationPermissionError


class FakeStudentNotificationRepository:
    def __init__(self, store: NotificationStore):
        self.store = store
        self.read_ids: set[uuid.UUID] = set()

    async def get_current_student_profile(self, user_id):
        if user_id == STUDENT_ID:
            institute_id = CECS_INSTITUTE_ID
            profile_id = PROFILE_ID
        elif user_id == OTHER_STUDENT_ID:
            institute_id = VIB_INSTITUTE_ID
            profile_id = OTHER_PROFILE_ID
        else:
            return None
        return {
            "id": profile_id,
            "student_id": "D2026",
            "program": None,
            "major": None,
            "cohort": 2026,
            "academic_year": 1,
            "student_status": "active",
            "preferred_language": "en",
            "advisor_name": None,
            "advisor_email": None,
            "ai_personalization_enabled": True,
            "institute": {
                "id": institute_id,
                "code": "CECS" if institute_id == CECS_INSTITUTE_ID else "VIB",
                "name_vi": "Institute",
                "name_en": "Institute",
            },
            "academic_summary": None,
        }

    async def get_notifications(self, *, user_id, profile, lang="en"):
        visible = []
        for row in self.store.rows.values():
            if row["status"] == "archived" or row["status"] == "draft":
                continue
            if row["status"] == "scheduled" and row["start_date"] and row["start_date"] > NOW:
                continue
            if row["target_scope"] == "institute" and row["institute_id"] != profile["institute"]["id"]:
                continue
            visible.append(
                {
                    **row,
                    "forum_topic_id": row.get("forum_topic_id"),
                    "forum_comment_id": row.get("forum_comment_id"),
                    "is_read": row["id"] in self.read_ids,
                    "important": False,
                    "archived": False,
                }
            )
        return visible

    async def mark_notification_read(self, *, notification_id, user_id, profile):
        visible = await self.get_notifications(user_id=user_id, profile=profile)
        if not any(row["id"] == notification_id for row in visible):
            return None
        self.read_ids.add(notification_id)
        return {"notification_id": notification_id, "is_read": True}

    async def mark_notification_unread(self, *, notification_id, user_id, profile):
        visible = await self.get_notifications(user_id=user_id, profile=profile)
        if not any(row["id"] == notification_id for row in visible):
            return None
        self.read_ids.discard(notification_id)
        return {"notification_id": notification_id, "is_read": False}

    async def mark_all_notifications_read(self, *, user_id, profile):
        visible = await self.get_notifications(user_id=user_id, profile=profile)
        unread = [row["id"] for row in visible if row["id"] not in self.read_ids]
        self.read_ids.update(unread)
        return len(unread)


def _app(current_user: AuthenticatedUser | None, store: NotificationStore) -> FastAPI:
    app = FastAPI()
    app.include_router(admin_notifications_router)
    app.include_router(students_router)

    if current_user is not None:

        async def fake_current_user():
            return current_user

        app.dependency_overrides[get_current_user] = fake_current_user

    async def fake_admin_repository():
        return FakeAdminNotificationRepository(store)

    async def fake_student_repository():
        return FakeStudentNotificationRepository(store)

    app.dependency_overrides[get_admin_notification_repository] = fake_admin_repository
    app.dependency_overrides[get_student_repository] = fake_student_repository
    return app


async def _request(app: FastAPI, method: str, path: str, json: dict | None = None):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.request(method, path, json=json)


def test_admin_notification_list_requires_auth():
    response = _run(_request(_app(None, NotificationStore()), "GET", "/admin/notifications"))

    assert response.status_code == 401


def test_student_cannot_list_admin_notifications():
    response = _run(
        _request(_app(_student(), NotificationStore()), "GET", "/admin/notifications")
    )

    assert response.status_code == 403


def test_admin_can_create_draft_and_draft_is_not_visible_to_student():
    store = NotificationStore()
    admin_app = _app(_global_admin(), store)

    created = _run(
        _request(
            admin_app,
            "POST",
            "/admin/notifications",
            {"title": "Draft", "message": "Not visible yet", "type": "academic"},
        )
    )
    student_notifications = _run(
        _request(_app(_student(), store), "GET", "/students/me/notifications")
    )

    assert created.status_code == 201
    assert created.json()["status"] == "draft"
    assert student_notifications.status_code == 200
    assert student_notifications.json() == []


def test_admin_notification_blank_title_is_rejected_with_controlled_validation():
    response = _run(
        _request(
            _app(_global_admin(), NotificationStore()),
            "POST",
            "/admin/notifications",
            {"title": "   ", "message": "Visible", "type": "academic"},
        )
    )

    assert response.status_code == 422
    assert "password" not in response.text.lower()
    assert "postgres" not in response.text.lower()


def test_admin_can_publish_all_student_notification_visible_to_student():
    store = NotificationStore()
    admin_app = _app(_global_admin(), store)
    created = _run(
        _request(
            admin_app,
            "POST",
            "/admin/notifications",
            {"title": "Published", "message": "Visible", "type": "academic"},
        )
    )

    published = _run(
        _request(
            admin_app,
            "POST",
            f"/admin/notifications/{created.json()['id']}/publish",
        )
    )
    student_notifications = _run(
        _request(_app(_student(), store), "GET", "/students/me/notifications")
    )

    assert published.status_code == 200
    assert published.json()["status"] == "published"
    assert student_notifications.status_code == 200
    assert student_notifications.json()[0]["title"] == "Published"


def test_institute_target_visible_only_to_matching_student():
    store = NotificationStore()
    admin_app = _app(_global_admin(), store)
    created = _run(
        _request(
            admin_app,
            "POST",
            "/admin/notifications",
            {
                "title": "CECS only",
                "message": "Institute notice",
                "type": "academic",
                "target_scope": "institute",
                "institute_id": str(CECS_INSTITUTE_ID),
            },
        )
    )
    _run(
        _request(
            admin_app,
            "POST",
            f"/admin/notifications/{created.json()['id']}/publish",
        )
    )

    cecs_notifications = _run(
        _request(_app(_student(STUDENT_ID), store), "GET", "/students/me/notifications")
    )
    vib_notifications = _run(
        _request(_app(_student(OTHER_STUDENT_ID), store), "GET", "/students/me/notifications")
    )

    assert cecs_notifications.status_code == 200
    assert cecs_notifications.json()[0]["title"] == "CECS only"
    assert vib_notifications.status_code == 200
    assert vib_notifications.json() == []


def test_student_notification_response_can_reference_forum_topic():
    forum_topic_id = uuid.UUID("77777777-7777-4777-8777-777777777777")
    store = NotificationStore()
    admin_app = _app(_global_admin(), store)
    created = _run(
        _request(
            admin_app,
            "POST",
            "/admin/notifications",
            {
                "title": "Forum topic",
                "message": "Discussion to review",
                "type": "forum",
                "forum_topic_id": str(forum_topic_id),
            },
        )
    )
    _run(
        _request(
            admin_app,
            "POST",
            f"/admin/notifications/{created.json()['id']}/publish",
        )
    )

    student_notifications = _run(
        _request(_app(_student(), store), "GET", "/students/me/notifications")
    )

    assert student_notifications.status_code == 200
    assert student_notifications.json()[0]["type"] == "forum"
    assert student_notifications.json()[0]["forum_topic_id"] == str(forum_topic_id)


def test_institute_admin_cannot_target_outside_scope():
    response = _run(
        _request(
            _app(_cecs_admin(), NotificationStore()),
            "POST",
            "/admin/notifications",
            {
                "title": "Global",
                "message": "Nope",
                "type": "academic",
                "target_scope": "all",
            },
        )
    )

    assert response.status_code == 403


def test_admin_can_schedule_future_notification_hidden_before_active_time():
    store = NotificationStore()
    admin_app = _app(_global_admin(), store)
    created = _run(
        _request(
            admin_app,
            "POST",
            "/admin/notifications",
            {"title": "Future", "message": "Later", "type": "academic"},
        )
    )

    scheduled = _run(
        _request(
            admin_app,
            "POST",
            f"/admin/notifications/{created.json()['id']}/schedule",
            {"publish_at": (NOW + timedelta(days=3)).isoformat()},
        )
    )
    student_notifications = _run(
        _request(_app(_student(), store), "GET", "/students/me/notifications")
    )

    assert scheduled.status_code == 200
    assert scheduled.json()["status"] == "scheduled"
    assert student_notifications.status_code == 200
    assert student_notifications.json() == []


def test_admin_schedule_rejects_invalid_end_date_window():
    store = NotificationStore()
    admin_app = _app(_global_admin(), store)
    created = _run(
        _request(
            admin_app,
            "POST",
            "/admin/notifications",
            {"title": "Bad window", "message": "Dates", "type": "academic"},
        )
    )

    response = _run(
        _request(
            admin_app,
            "POST",
            f"/admin/notifications/{created.json()['id']}/schedule",
            {
                "publish_at": (NOW + timedelta(days=3)).isoformat(),
                "end_date": (NOW + timedelta(days=1)).isoformat(),
            },
        )
    )

    assert response.status_code == 422


def test_admin_can_archive_notification_and_hide_from_student():
    store = NotificationStore()
    admin_app = _app(_global_admin(), store)
    created = _run(
        _request(
            admin_app,
            "POST",
            "/admin/notifications",
            {"title": "Archive me", "message": "Visible briefly", "type": "academic"},
        )
    )
    notification_id = created.json()["id"]
    _run(_request(admin_app, "POST", f"/admin/notifications/{notification_id}/publish"))

    archived = _run(
        _request(admin_app, "POST", f"/admin/notifications/{notification_id}/archive")
    )
    student_notifications = _run(
        _request(_app(_student(), store), "GET", "/students/me/notifications")
    )

    assert archived.status_code == 200
    assert archived.json()["status"] == "archived"
    assert student_notifications.status_code == 200
    assert student_notifications.json() == []


def test_admin_publish_and_archive_actions_are_idempotent():
    store = NotificationStore()
    admin_app = _app(_global_admin(), store)
    created = _run(
        _request(
            admin_app,
            "POST",
            "/admin/notifications",
            {"title": "Repeatable", "message": "Lifecycle", "type": "academic"},
        )
    )
    notification_id = created.json()["id"]

    first_publish = _run(
        _request(admin_app, "POST", f"/admin/notifications/{notification_id}/publish")
    )
    second_publish = _run(
        _request(admin_app, "POST", f"/admin/notifications/{notification_id}/publish")
    )
    first_archive = _run(
        _request(admin_app, "POST", f"/admin/notifications/{notification_id}/archive")
    )
    second_archive = _run(
        _request(admin_app, "POST", f"/admin/notifications/{notification_id}/archive")
    )

    assert first_publish.status_code == 200
    assert second_publish.status_code == 200
    assert first_archive.status_code == 200
    assert second_archive.status_code == 200
    assert second_archive.json()["status"] == "archived"


def test_student_read_unread_works_with_admin_created_notification():
    store = NotificationStore()
    admin_app = _app(_global_admin(), store)
    created = _run(
        _request(
            admin_app,
            "POST",
            "/admin/notifications",
            {"title": "Read me", "message": "Visible", "type": "academic"},
        )
    )
    notification_id = created.json()["id"]
    _run(_request(admin_app, "POST", f"/admin/notifications/{notification_id}/publish"))
    student_app = _app(_student(), store)

    read = _run(
        _request(student_app, "POST", f"/students/me/notifications/{notification_id}/read")
    )
    unread = _run(
        _request(student_app, "POST", f"/students/me/notifications/{notification_id}/unread")
    )

    assert read.status_code == 200
    assert read.json() == {"notification_id": notification_id, "is_read": True}
    assert unread.status_code == 200
    assert unread.json() == {"notification_id": notification_id, "is_read": False}
