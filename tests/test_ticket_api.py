from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from vinchatbot.app.api.routes_tickets import get_ticket_repository
from vinchatbot.app.api.routes_tickets import router as tickets_router
from vinchatbot.app.dependencies.auth import get_current_user
from vinchatbot.app.repositories.auth import AuthenticatedUser

STUDENT_USER_ID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
OTHER_STUDENT_USER_ID = uuid.UUID("99999999-9999-9999-9999-999999999999")
GLOBAL_ADMIN_USER_ID = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
INSTITUTE_ADMIN_USER_ID = uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
STUDENT_PROFILE_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
OTHER_PROFILE_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
CECS_ID = uuid.UUID("33333333-3333-3333-3333-333333333333")
VIB_ID = uuid.UUID("44444444-4444-4444-4444-444444444444")
TICKET_ID = uuid.UUID("55555555-5555-5555-5555-555555555555")
OTHER_TICKET_ID = uuid.UUID("66666666-6666-6666-6666-666666666666")
MESSAGE_ID = uuid.UUID("77777777-7777-7777-7777-777777777777")
HISTORY_ID = uuid.UUID("88888888-8888-8888-8888-888888888888")
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
        student_profile={"id": STUDENT_PROFILE_ID},
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


class FakeTicketRepository:
    def __init__(self) -> None:
        self.student_user_ids_seen: list[uuid.UUID] = []
        self.status_history_created = False
        self.tickets = {
            TICKET_ID: self._ticket(
                ticket_id=TICKET_ID,
                student_profile_id=STUDENT_PROFILE_ID,
                institute_id=CECS_ID,
                institute_code="CECS",
                student_name="Demo CECS Student",
            ),
            OTHER_TICKET_ID: self._ticket(
                ticket_id=OTHER_TICKET_ID,
                student_profile_id=OTHER_PROFILE_ID,
                institute_id=VIB_ID,
                institute_code="VIB",
                student_name="Demo Business Student",
            ),
        }

    def _ticket(
        self,
        *,
        ticket_id: uuid.UUID,
        student_profile_id: uuid.UUID,
        institute_id: uuid.UUID,
        institute_code: str,
        student_name: str,
    ) -> dict[str, Any]:
        return {
            "id": ticket_id,
            "student_profile_id": student_profile_id,
            "student_id": "D2026CECS001",
            "student_name": student_name,
            "institute_id": institute_id,
            "institute_code": institute_code,
            "subject": "Registration support",
            "body": "I need help with course registration.",
            "department": "Registrar",
            "category": "registration",
            "priority": "medium",
            "status": "submitted",
            "confirmed_by_user": True,
            "created_by_ai": False,
            "include_chat_context": False,
            "included_context": None,
            "source_conversation_id": None,
            "origin_question": None,
            "assigned_admin_id": None,
            "assignee": None,
            "submitted_at": NOW,
            "due_at": None,
            "sla_hours": None,
            "resolution": None,
            "archived": False,
            "deleted": False,
            "created_at": NOW,
            "updated_at": NOW,
            "messages": [],
            "status_history": [],
            "password_hash": "must-not-leak",
            "token_hash": "must-not-leak",
        }

    async def list_student_tickets(self, user_id):
        self.student_user_ids_seen.append(user_id)
        if user_id != STUDENT_USER_ID:
            return []
        return [self.tickets[TICKET_ID]]

    async def get_student_ticket(self, *, ticket_id, user_id):
        self.student_user_ids_seen.append(user_id)
        if user_id != STUDENT_USER_ID or ticket_id != TICKET_ID:
            return None
        return self.tickets[TICKET_ID]

    async def create_student_ticket(self, *, user_id, request):
        self.student_user_ids_seen.append(user_id)
        if user_id != STUDENT_USER_ID:
            return None
        ticket = self._ticket(
            ticket_id=uuid.UUID("12121212-1212-1212-1212-121212121212"),
            student_profile_id=STUDENT_PROFILE_ID,
            institute_id=CECS_ID,
            institute_code="CECS",
            student_name="Demo CECS Student",
        )
        ticket.update(
            {
                "subject": request.subject,
                "body": request.body,
                "category": request.category,
                "department": request.department,
                "priority": request.priority,
                "status": "submitted",
                "confirmed_by_user": True,
                "created_by_ai": getattr(request, "created_by_ai", False),
                "include_chat_context": request.include_chat_context,
                "included_context": (
                    request.included_context if request.include_chat_context else None
                ),
                "source_conversation_id": request.source_conversation_id,
                "origin_question": request.origin_question,
                "submitted_at": NOW,
            }
        )
        return ticket

    async def add_student_message(self, *, ticket_id, user_id, request):
        self.student_user_ids_seen.append(user_id)
        if user_id != STUDENT_USER_ID or ticket_id != TICKET_ID:
            return None
        return self._message(ticket_id=ticket_id, sender_user_id=user_id, author_type="student", body=request.body)

    async def list_admin_tickets(self, *, current_user, filters):
        visible = list(self.tickets.values())
        if "global_admin" not in current_user.roles:
            institute_id = current_user.institute["id"] if current_user.institute else None
            visible = [ticket for ticket in visible if ticket["institute_id"] == institute_id]
        if filters.status:
            visible = [ticket for ticket in visible if ticket["status"] == filters.status]
        if filters.priority:
            visible = [ticket for ticket in visible if ticket["priority"] == filters.priority]
        return visible

    async def get_admin_ticket(self, *, ticket_id, current_user):
        visible = await self.list_admin_tickets(
            current_user=current_user,
            filters=_EmptyFilters(),
        )
        for ticket in visible:
            if ticket["id"] == ticket_id:
                return ticket
        return None

    async def update_admin_ticket(self, *, ticket_id, current_user, request):
        ticket = await self.get_admin_ticket(ticket_id=ticket_id, current_user=current_user)
        if ticket is None:
            return None
        old_status = ticket["status"]
        if request.status is not None:
            ticket["status"] = request.status
        if request.priority is not None:
            ticket["priority"] = request.priority
        if request.assigned_admin_id is not None:
            ticket["assigned_admin_id"] = request.assigned_admin_id
            ticket["assignee"] = current_user.full_name
        if request.resolution is not None:
            ticket["resolution"] = request.resolution
        if request.archived is not None:
            ticket["archived"] = request.archived
        if request.status is not None and request.status != old_status:
            self.status_history_created = True
            ticket["status_history"] = [
                {
                    "id": HISTORY_ID,
                    "old_status": old_status,
                    "new_status": request.status,
                    "changed_by": current_user.id,
                    "changed_by_email": current_user.email,
                    "changed_by_full_name": current_user.full_name,
                    "changed_at": NOW,
                }
            ]
        return ticket

    async def add_admin_message(self, *, ticket_id, current_user, request):
        if await self.get_admin_ticket(ticket_id=ticket_id, current_user=current_user) is None:
            return None
        return self._message(
            ticket_id=ticket_id,
            sender_user_id=current_user.id,
            author_type="admin",
            body=request.body,
        )

    def _message(
        self,
        *,
        ticket_id: uuid.UUID,
        sender_user_id: uuid.UUID,
        author_type: str,
        body: str,
    ) -> dict[str, Any]:
        return {
            "id": MESSAGE_ID,
            "ticket_id": ticket_id,
            "sender_user_id": sender_user_id,
            "sender_email": "student.cs.demo@vinuni.edu.vn"
            if author_type == "student"
            else "admin.cecs.demo@vinuni.edu.vn",
            "sender_full_name": "Demo CECS Student"
            if author_type == "student"
            else "Demo CECS Admin",
            "author_type": author_type,
            "body": body,
            "created_at": NOW,
            "password_hash": "must-not-leak",
            "token_hash": "must-not-leak",
        }


class _EmptyFilters:
    status = None
    priority = None
    include_archived = False


def _ticket_app(
    *,
    current_user: AuthenticatedUser | None = None,
    repository: FakeTicketRepository | None = None,
) -> FastAPI:
    app = FastAPI()
    app.include_router(tickets_router)

    if current_user is not None:

        async def fake_current_user():
            return current_user

        app.dependency_overrides[get_current_user] = fake_current_user

    if repository is not None:

        async def fake_ticket_repository():
            return repository

        app.dependency_overrides[get_ticket_repository] = fake_ticket_repository

    return app


async def _request(method: str, path: str, app: FastAPI, **kwargs):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.request(method, path, **kwargs)


def test_student_list_only_own_tickets():
    repository = FakeTicketRepository()
    response = _run(
        _request(
            "GET",
            "/tickets/me",
            _ticket_app(current_user=_student_user(), repository=repository),
        )
    )

    body = response.json()
    assert response.status_code == 200
    assert [ticket["id"] for ticket in body] == [str(TICKET_ID)]
    assert body[0]["student_profile_id"] == str(STUDENT_PROFILE_ID)
    assert repository.student_user_ids_seen == [STUDENT_USER_ID]


def test_student_cannot_access_another_students_ticket():
    response = _run(
        _request(
            "GET",
            f"/tickets/{OTHER_TICKET_ID}",
            _ticket_app(current_user=_student_user(), repository=FakeTicketRepository()),
        )
    )

    assert response.status_code == 404


def test_student_can_create_ticket():
    response = _run(
        _request(
            "POST",
            "/tickets",
            _ticket_app(current_user=_student_user(), repository=FakeTicketRepository()),
            json={
                "subject": "Need enrollment help",
                "body": "I cannot enroll in CSC202.",
                "department": "Registrar",
                "category": "enrollment",
                "priority": "high",
                "include_chat_context": True,
                "included_context": "Short safe context.",
                "origin_question": "Why can't I enroll?",
            },
        )
    )

    body = response.json()
    assert response.status_code == 201
    assert body["subject"] == "Need enrollment help"
    assert body["status"] == "submitted"
    assert body["priority"] == "high"
    assert body["confirmed_by_user"] is True
    assert body["created_by_ai"] is False
    assert body["submitted_at"] is not None


def test_ai_drafted_flag_persists_on_create():
    response = _run(
        _request(
            "POST",
            "/tickets",
            _ticket_app(current_user=_student_user(), repository=FakeTicketRepository()),
            json={
                "subject": "Vinnie-drafted: Canvas login",
                "body": "I can't log into Canvas.",
                "category": "technical",
                "priority": "medium",
                "created_by_ai": True,
            },
        )
    )

    body = response.json()
    assert response.status_code == 201
    assert body["created_by_ai"] is True
    assert body["confirmed_by_user"] is True  # the drawer is the confirm step


def test_student_can_request_ticket_suggestion(monkeypatch):
    import vinchatbot.app.api.routes_tickets as rt
    from vinchatbot.app.schemas.tickets import SuggestedTicketDraft

    async def fake_suggest(request):
        return SuggestedTicketDraft(
            subject="Cannot log into Canvas",
            body="I am unable to log into Canvas and need help.",
            category="technical",
        )

    monkeypatch.setattr(rt, "suggest_ticket_draft", fake_suggest)
    response = _run(
        _request(
            "POST",
            "/tickets/suggest",
            _ticket_app(current_user=_student_user()),
            json={"origin_question": "I can't log into Canvas", "answer": "Try resetting your password."},
        )
    )

    body = response.json()
    assert response.status_code == 200
    assert body["subject"] == "Cannot log into Canvas"
    assert body["category"] == "technical"


def test_non_student_cannot_request_ticket_suggestion():
    response = _run(
        _request(
            "POST",
            "/tickets/suggest",
            _ticket_app(current_user=_global_admin_user()),
            json={"origin_question": "anything"},
        )
    )

    assert response.status_code == 403


def test_student_can_add_message_to_own_ticket():
    response = _run(
        _request(
            "POST",
            f"/tickets/{TICKET_ID}/messages",
            _ticket_app(current_user=_student_user(), repository=FakeTicketRepository()),
            json={"body": "Adding more details."},
        )
    )

    body = response.json()
    assert response.status_code == 200
    assert body["ticket_id"] == str(TICKET_ID)
    assert body["author_type"] == "student"
    assert body["body"] == "Adding more details."


def test_global_admin_can_list_all_tickets():
    response = _run(
        _request(
            "GET",
            "/admin/tickets",
            _ticket_app(current_user=_global_admin_user(), repository=FakeTicketRepository()),
        )
    )

    body = response.json()
    assert response.status_code == 200
    assert {ticket["id"] for ticket in body} == {str(TICKET_ID), str(OTHER_TICKET_ID)}


def test_institute_admin_sees_only_own_institute_tickets():
    response = _run(
        _request(
            "GET",
            "/admin/tickets",
            _ticket_app(
                current_user=_institute_admin_user(),
                repository=FakeTicketRepository(),
            ),
        )
    )

    body = response.json()
    assert response.status_code == 200
    assert [ticket["id"] for ticket in body] == [str(TICKET_ID)]
    assert body[0]["institute_code"] == "CECS"


def test_admin_ticket_filters_validate_allowed_values():
    response = _run(
        _request(
            "GET",
            "/admin/tickets?status=not-a-status",
            _ticket_app(current_user=_global_admin_user(), repository=FakeTicketRepository()),
        )
    )

    assert response.status_code == 422
    assert response.json()["detail"][0]["type"] == "value_error"


def test_admin_status_update_creates_status_history():
    repository = FakeTicketRepository()
    response = _run(
        _request(
            "PATCH",
            f"/admin/tickets/{TICKET_ID}",
            _ticket_app(current_user=_global_admin_user(), repository=repository),
            json={"status": "in_progress", "priority": "urgent"},
        )
    )

    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "in_progress"
    assert body["priority"] == "urgent"
    assert repository.status_history_created is True
    assert body["status_history"][0]["old_status"] == "submitted"
    assert body["status_history"][0]["new_status"] == "in_progress"


def test_non_admin_rejected_from_admin_endpoints():
    response = _run(
        _request(
            "GET",
            "/admin/tickets",
            _ticket_app(current_user=_student_user(), repository=FakeTicketRepository()),
        )
    )

    assert response.status_code == 403


def test_ticket_api_responses_do_not_expose_sensitive_fields():
    app = _ticket_app(current_user=_student_user(), repository=FakeTicketRepository())

    tickets = _run(_request("GET", "/tickets/me", app))
    detail = _run(_request("GET", f"/tickets/{TICKET_ID}", app))
    message = _run(
        _request(
            "POST",
            f"/tickets/{TICKET_ID}/messages",
            app,
            json={"body": "More context."},
        )
    )
    combined = f"{tickets.json()}\n{detail.json()}\n{message.json()}"

    assert tickets.status_code == 200
    assert detail.status_code == 200
    assert message.status_code == 200
    assert "password_hash" not in combined
    assert "token_hash" not in combined
