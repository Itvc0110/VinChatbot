from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from vinchatbot.app.api.routes_conversations import get_conversation_repository
from vinchatbot.app.api.routes_conversations import router as conversations_router
from vinchatbot.app.dependencies.auth import get_current_user
from vinchatbot.app.repositories.auth import AuthenticatedUser
from vinchatbot.app.repositories.conversations import derive_conversation_title

USER_ID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
OTHER_USER_ID = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
CONVERSATION_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
OTHER_CONVERSATION_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
NEW_CONVERSATION_ID = uuid.UUID("33333333-3333-3333-3333-333333333333")
USER_MESSAGE_ID = uuid.UUID("44444444-4444-4444-4444-444444444444")
ASSISTANT_MESSAGE_ID = uuid.UUID("55555555-5555-5555-5555-555555555555")
NOW = datetime(2026, 6, 27, 9, 0, tzinfo=UTC)


def _run(awaitable):
    return asyncio.run(asyncio.wait_for(awaitable, timeout=2.0))


def _current_user() -> AuthenticatedUser:
    return AuthenticatedUser(
        id=USER_ID,
        email="student.cs.demo@vinuni.edu.vn",
        full_name="Demo CECS Student",
        preferred_name="CECS Student",
        status="active",
        roles=("student",),
    )


class FakeConversationRepository:
    def __init__(self) -> None:
        self.user_ids_seen: list[uuid.UUID] = []
        self.deleted_ids: list[uuid.UUID] = []
        self.messages_by_conversation = {
            CONVERSATION_ID: [
                self._message(
                    message_id=ASSISTANT_MESSAGE_ID,
                    role="assistant",
                    content="The add/drop deadline is Friday.",
                    created_at=NOW + timedelta(minutes=1),
                ),
                self._message(
                    message_id=USER_MESSAGE_ID,
                    role="user",
                    content="When is add/drop?",
                    created_at=NOW,
                ),
            ],
            OTHER_CONVERSATION_ID: [],
        }
        self.conversations = {
            CONVERSATION_ID: self._conversation(
                conversation_id=CONVERSATION_ID,
                user_id=USER_ID,
                title="Academic deadlines",
                last_message_at=NOW + timedelta(minutes=1),
            ),
            OTHER_CONVERSATION_ID: self._conversation(
                conversation_id=OTHER_CONVERSATION_ID,
                user_id=OTHER_USER_ID,
                title="Other student's chat",
                last_message_at=NOW + timedelta(minutes=2),
            ),
        }

    def _conversation(
        self,
        *,
        conversation_id: uuid.UUID,
        user_id: uuid.UUID,
        title: str,
        last_message_at: datetime | None,
    ) -> dict[str, Any]:
        return {
            "id": conversation_id,
            "user_id": user_id,
            "title": title,
            "title_manual": title != "New conversation",
            "topic": "academic",
            "created_at": NOW,
            "updated_at": NOW,
            "last_message_at": last_message_at,
            "password_hash": "must-not-leak",
            "token_hash": "must-not-leak",
        }

    def _message(
        self,
        *,
        message_id: uuid.UUID,
        role: str,
        content: str,
        created_at: datetime,
    ) -> dict[str, Any]:
        return {
            "id": message_id,
            "conversation_id": CONVERSATION_ID,
            "role": role,
            "content": content,
            "answer_json": {"safe": True} if role == "assistant" else None,
            "intent": "calendar" if role == "assistant" else None,
            "topic": "academic",
            "confidence": 0.91 if role == "assistant" else None,
            "needs_human_review": False,
            "created_at": created_at,
            "password_hash": "must-not-leak",
            "token_hash": "must-not-leak",
        }

    async def list_conversations(self, user_id):
        self.user_ids_seen.append(user_id)
        return [
            self._summary(conversation)
            for conversation in sorted(
                self.conversations.values(),
                key=lambda item: item["last_message_at"] or item["updated_at"],
                reverse=True,
            )
            if conversation["user_id"] == user_id
        ]

    async def create_conversation(self, *, user_id, request):
        self.user_ids_seen.append(user_id)
        title = request.title or derive_conversation_title(request.initial_message)
        conversation = self._conversation(
            conversation_id=NEW_CONVERSATION_ID,
            user_id=user_id,
            title=title,
            last_message_at=NOW if request.initial_message else None,
        )
        conversation["title_manual"] = request.title is not None
        messages = []
        if request.initial_message:
            messages = [
                {
                    **self._message(
                        message_id=uuid.UUID("66666666-6666-6666-6666-666666666666"),
                        role="user",
                        content=request.initial_message,
                        created_at=NOW,
                    ),
                    "conversation_id": NEW_CONVERSATION_ID,
                }
            ]
        return {**self._summary(conversation), "messages": messages}

    async def get_conversation(self, *, user_id, conversation_id):
        self.user_ids_seen.append(user_id)
        conversation = self.conversations.get(conversation_id)
        if conversation is None or conversation["user_id"] != user_id:
            return None
        return {
            **self._summary(conversation),
            "messages": await self.list_messages(
                user_id=user_id,
                conversation_id=conversation_id,
            ),
        }

    async def list_messages(self, *, user_id, conversation_id):
        conversation = self.conversations.get(conversation_id)
        if conversation is None or conversation["user_id"] != user_id:
            return None
        return sorted(
            self.messages_by_conversation[conversation_id],
            key=lambda message: (message["created_at"], message["id"]),
        )

    async def update_conversation(self, *, user_id, conversation_id, request):
        self.user_ids_seen.append(user_id)
        conversation = self.conversations.get(conversation_id)
        if conversation is None or conversation["user_id"] != user_id:
            return None
        if request.title is not None:
            conversation["title"] = request.title
            conversation["title_manual"] = True
        if request.topic is not None:
            conversation["topic"] = request.topic
        return {
            **self._summary(conversation),
            "messages": await self.list_messages(
                user_id=user_id,
                conversation_id=conversation_id,
            ),
        }

    async def delete_conversation(self, *, user_id, conversation_id):
        self.user_ids_seen.append(user_id)
        conversation = self.conversations.get(conversation_id)
        if conversation is None or conversation["user_id"] != user_id:
            return False
        self.deleted_ids.append(conversation_id)
        return True

    def _summary(self, conversation: dict[str, Any]) -> dict[str, Any]:
        return {
            key: value
            for key, value in conversation.items()
            if key
            in {
                "id",
                "title",
                "title_manual",
                "topic",
                "created_at",
                "updated_at",
                "last_message_at",
                "password_hash",
                "token_hash",
            }
        }


def _conversation_app(
    *,
    current_user: AuthenticatedUser | None = None,
    repository: FakeConversationRepository | None = None,
) -> FastAPI:
    app = FastAPI()
    app.include_router(conversations_router)

    if current_user is not None:

        async def fake_current_user():
            return current_user

        app.dependency_overrides[get_current_user] = fake_current_user

    if repository is not None:

        async def fake_conversation_repository():
            return repository

        app.dependency_overrides[get_conversation_repository] = fake_conversation_repository

    return app


async def _request(method: str, path: str, app: FastAPI, **kwargs):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.request(method, path, **kwargs)


def test_conversation_routes_require_auth():
    response = _run(
        _request(
            "GET",
            "/conversations",
            _conversation_app(repository=FakeConversationRepository()),
        )
    )

    assert response.status_code == 401


def test_user_lists_only_own_conversations():
    repository = FakeConversationRepository()
    response = _run(
        _request(
            "GET",
            "/conversations",
            _conversation_app(current_user=_current_user(), repository=repository),
        )
    )

    body = response.json()
    assert response.status_code == 200
    assert [conversation["id"] for conversation in body] == [str(CONVERSATION_ID)]
    assert body[0]["title"] == "Academic deadlines"
    assert repository.user_ids_seen == [USER_ID]


def test_cross_user_conversation_access_returns_404():
    response = _run(
        _request(
            "GET",
            f"/conversations/{OTHER_CONVERSATION_ID}",
            _conversation_app(
                current_user=_current_user(),
                repository=FakeConversationRepository(),
            ),
        )
    )

    assert response.status_code == 404


def test_create_conversation_derives_title_from_initial_message():
    response = _run(
        _request(
            "POST",
            "/conversations",
            _conversation_app(
                current_user=_current_user(),
                repository=FakeConversationRepository(),
            ),
            json={
                "initial_message": "  When is the course add/drop deadline this semester?  ",
                "topic": "academic",
            },
        )
    )

    body = response.json()
    assert response.status_code == 201
    assert body["id"] == str(NEW_CONVERSATION_ID)
    assert body["title"] == "When is the course add/drop deadline this semester?"
    assert body["title_manual"] is False
    assert body["messages"][0]["role"] == "user"


def test_messages_are_ordered_oldest_first():
    response = _run(
        _request(
            "GET",
            f"/conversations/{CONVERSATION_ID}/messages",
            _conversation_app(
                current_user=_current_user(),
                repository=FakeConversationRepository(),
            ),
        )
    )

    body = response.json()
    assert response.status_code == 200
    assert [message["role"] for message in body] == ["user", "assistant"]


def test_rename_update_conversation():
    response = _run(
        _request(
            "PATCH",
            f"/conversations/{CONVERSATION_ID}",
            _conversation_app(
                current_user=_current_user(),
                repository=FakeConversationRepository(),
            ),
            json={"title": "Renamed chat", "topic": "registration"},
        )
    )

    body = response.json()
    assert response.status_code == 200
    assert body["title"] == "Renamed chat"
    assert body["title_manual"] is True
    assert body["topic"] == "registration"


def test_delete_conversation_is_scoped_to_current_user():
    repository = FakeConversationRepository()
    response = _run(
        _request(
            "DELETE",
            f"/conversations/{CONVERSATION_ID}",
            _conversation_app(current_user=_current_user(), repository=repository),
        )
    )
    cross_user_response = _run(
        _request(
            "DELETE",
            f"/conversations/{OTHER_CONVERSATION_ID}",
            _conversation_app(current_user=_current_user(), repository=repository),
        )
    )

    assert response.status_code == 200
    assert response.json() == {"deleted": True}
    assert repository.deleted_ids == [CONVERSATION_ID]
    assert cross_user_response.status_code == 404


def test_conversation_responses_do_not_expose_sensitive_fields():
    app = _conversation_app(
        current_user=_current_user(),
        repository=FakeConversationRepository(),
    )

    conversations = _run(_request("GET", "/conversations", app))
    detail = _run(_request("GET", f"/conversations/{CONVERSATION_ID}", app))
    messages = _run(_request("GET", f"/conversations/{CONVERSATION_ID}/messages", app))
    combined = f"{conversations.json()}\n{detail.json()}\n{messages.json()}"

    assert conversations.status_code == 200
    assert detail.status_code == 200
    assert messages.status_code == 200
    assert "password_hash" not in combined
    assert "token_hash" not in combined


def test_derived_title_is_deterministic_and_bounded():
    title = derive_conversation_title(
        "   Please explain course registration, prerequisite checks, and waitlist rules.   "
    )

    assert title == "Please explain course registration, prerequisite checks, and..."
    assert len(title) <= 64
    assert derive_conversation_title(None) == "New conversation"
