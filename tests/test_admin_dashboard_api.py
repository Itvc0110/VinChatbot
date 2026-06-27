from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from vinchatbot.app.api.routes_admin_dashboard import get_admin_dashboard_repository
from vinchatbot.app.api.routes_admin_dashboard import router as admin_dashboard_router
from vinchatbot.app.dependencies.auth import get_current_user
from vinchatbot.app.repositories.auth import AuthenticatedUser

STUDENT_USER_ID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
GLOBAL_ADMIN_USER_ID = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
INSTITUTE_ADMIN_USER_ID = uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
CECS_ID = uuid.UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")
VIB_ID = uuid.UUID("eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee")
TICKET_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
OTHER_TICKET_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
DEADLINE_ID = uuid.UUID("33333333-3333-3333-3333-333333333333")
NOW = datetime(2026, 6, 26, 12, 0, tzinfo=UTC)


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
        institute={"id": CECS_ID, "code": "CECS"},
    )


def _global_admin_user() -> AuthenticatedUser:
    return AuthenticatedUser(
        id=GLOBAL_ADMIN_USER_ID,
        email="admin.global.demo@vinuni.edu.vn",
        full_name="Demo Global Admin",
        preferred_name="Global Admin",
        status="active",
        roles=("global_admin",),
    )


def _institute_admin_user() -> AuthenticatedUser:
    return AuthenticatedUser(
        id=INSTITUTE_ADMIN_USER_ID,
        email="admin.cecs.demo@vinuni.edu.vn",
        full_name="Demo CECS Admin",
        preferred_name="CECS Admin",
        status="active",
        roles=("institute_admin",),
        institute={"id": CECS_ID, "code": "CECS"},
    )


class FakeAdminDashboardRepository:
    async def get_dashboard(self, current_user: AuthenticatedUser) -> dict[str, Any]:
        is_global = "global_admin" in current_user.roles
        ticket_rows = [
            self._ticket(
                ticket_id=TICKET_ID,
                subject="Registration support",
                status="submitted",
                priority="urgent",
                institute_id=CECS_ID,
                institute_code="CECS",
                student_id="D2026CECS001",
                student_name="Demo CECS Student",
            ),
            self._ticket(
                ticket_id=OTHER_TICKET_ID,
                subject="Scholarship question",
                status="resolved",
                priority="medium",
                institute_id=VIB_ID,
                institute_code="VIB",
                student_id="D2026VIB001",
                student_name="Demo Business Student",
            ),
        ]
        visible_tickets = ticket_rows if is_global else [ticket_rows[0]]
        total_students = 4 if is_global else 1
        student_counts = [
            {
                "institute_id": CECS_ID,
                "institute_code": "CECS",
                "institute_name_en": "College of Engineering and Computer Science",
                "institute_name_vi": "Viện Kỹ thuật và Khoa học Máy tính",
                "student_count": 1,
            }
        ]
        if is_global:
            student_counts.append(
                {
                    "institute_id": VIB_ID,
                    "institute_code": "VIB",
                    "institute_name_en": "College of Business and Management",
                    "institute_name_vi": "Viện Kinh doanh Quản trị",
                    "student_count": 1,
                }
            )

        return {
            "scope": {
                "kind": "global" if is_global else "institute",
                "institute_id": None if is_global else CECS_ID,
                "institute_code": None if is_global else "CECS",
            },
            "overview": {
                "total_users": total_students + 2,
                "total_students": total_students,
                "total_institutes": 2 if is_global else 1,
                "total_tickets": len(visible_tickets),
                "open_tickets": sum(ticket["status"] != "resolved" for ticket in visible_tickets),
                "need_admin_response": sum(
                    ticket["status"] in {"submitted", "open", "in_progress"}
                    for ticket in visible_tickets
                ),
                "urgent_tickets": sum(ticket["priority"] == "urgent" for ticket in visible_tickets),
                "upcoming_deadlines": 2 if is_global else 1,
                "upcoming_schedules": 3 if is_global else 1,
                "upcoming_events": 1,
                "published_notifications": 2 if is_global else 1,
            },
            "ticket_counts_by_status": self._counts(
                visible_tickets,
                keys=("submitted", "open", "in_progress", "waiting_on_student", "resolved", "closed"),
                field="status",
            ),
            "ticket_counts_by_priority": self._counts(
                visible_tickets,
                keys=("low", "medium", "high", "urgent"),
                field="priority",
            ),
            "student_counts_by_institute": student_counts,
            "recent_tickets": visible_tickets,
            "upcoming_items": [
                {
                    "id": DEADLINE_ID,
                    "item_type": "deadline",
                    "title": "CSC202 Assignment 1",
                    "starts_at": NOW + timedelta(days=7),
                    "ends_at": None,
                    "course_code": "CSC202",
                    "institute_id": CECS_ID,
                    "institute_code": "CECS",
                    "source_title": "Demo academic seed",
                    "source_url": None,
                }
            ],
            "password_hash": "must-not-leak",
            "token_hash": "must-not-leak",
        }

    def _ticket(
        self,
        *,
        ticket_id: uuid.UUID,
        subject: str,
        status: str,
        priority: str,
        institute_id: uuid.UUID,
        institute_code: str,
        student_id: str,
        student_name: str,
    ) -> dict[str, Any]:
        return {
            "id": ticket_id,
            "subject": subject,
            "status": status,
            "priority": priority,
            "student_id": student_id,
            "student_name": student_name,
            "institute_id": institute_id,
            "institute_code": institute_code,
            "due_at": NOW + timedelta(days=2),
            "created_at": NOW,
            "updated_at": NOW + timedelta(hours=1),
            "password_hash": "must-not-leak",
            "token_hash": "must-not-leak",
        }

    def _counts(
        self,
        rows: list[dict[str, Any]],
        *,
        keys: tuple[str, ...],
        field: str,
    ) -> list[dict[str, Any]]:
        return [
            {"key": key, "count": sum(row[field] == key for row in rows)}
            for key in keys
        ]


def _dashboard_app(
    *,
    current_user: AuthenticatedUser | None = None,
    repository: FakeAdminDashboardRepository | None = None,
) -> FastAPI:
    app = FastAPI()
    app.include_router(admin_dashboard_router)

    if current_user is not None:

        async def fake_current_user():
            return current_user

        app.dependency_overrides[get_current_user] = fake_current_user

    if repository is not None:

        async def fake_dashboard_repository():
            return repository

        app.dependency_overrides[get_admin_dashboard_repository] = fake_dashboard_repository

    return app


async def _get(path: str, app: FastAPI):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.get(path)


def test_admin_dashboard_requires_auth():
    response = _run(_get("/admin/dashboard", _dashboard_app()))

    assert response.status_code == 401


def test_student_is_rejected_from_admin_dashboard():
    response = _run(
        _get(
            "/admin/dashboard",
            _dashboard_app(
                current_user=_student_user(),
                repository=FakeAdminDashboardRepository(),
            ),
        )
    )

    assert response.status_code == 403


def test_global_admin_can_read_dashboard_shape():
    response = _run(
        _get(
            "/admin/dashboard",
            _dashboard_app(
                current_user=_global_admin_user(),
                repository=FakeAdminDashboardRepository(),
            ),
        )
    )

    body = response.json()
    assert response.status_code == 200
    assert body["scope"]["kind"] == "global"
    assert body["overview"]["total_students"] >= 4
    assert body["overview"]["total_tickets"] >= 2
    assert {row["key"] for row in body["ticket_counts_by_status"]} >= {
        "submitted",
        "resolved",
    }
    assert any(row["student_count"] > 0 for row in body["student_counts_by_institute"])
    assert body["recent_tickets"]
    assert body["upcoming_items"]
    assert "password_hash" not in str(body)
    assert "token_hash" not in str(body)


def test_institute_admin_dashboard_is_scoped_to_institute():
    response = _run(
        _get(
            "/admin/dashboard",
            _dashboard_app(
                current_user=_institute_admin_user(),
                repository=FakeAdminDashboardRepository(),
            ),
        )
    )

    body = response.json()
    assert response.status_code == 200
    assert body["scope"]["kind"] == "institute"
    assert body["scope"]["institute_code"] == "CECS"
    assert body["overview"]["total_students"] >= 1
    assert {ticket["institute_code"] for ticket in body["recent_tickets"]} == {"CECS"}
