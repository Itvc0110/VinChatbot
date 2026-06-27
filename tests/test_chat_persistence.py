from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient

from vinchatbot.app.api import routes_chat
from vinchatbot.app.repositories.auth import AuthenticatedUser
from vinchatbot.app.schemas.chat import ChatRequest, ChatResponse

USER_ID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
NEW_CONVERSATION_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
EXISTING_CONVERSATION_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
OTHER_CONVERSATION_ID = uuid.UUID("33333333-3333-3333-3333-333333333333")
NOW = datetime(2026, 6, 27, 10, 0, tzinfo=UTC)


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
    def __init__(self, *, fail_create: bool = False) -> None:
        self.fail_create = fail_create
        self.created_for: list[uuid.UUID] = []
        self.appended: list[dict[str, Any]] = []

    async def create_conversation(self, *, user_id, request):
        if self.fail_create:
            raise RuntimeError("database unavailable")
        self.created_for.append(user_id)
        return {
            "id": NEW_CONVERSATION_ID,
            "title": "New conversation",
            "title_manual": False,
            "topic": request.topic,
            "created_at": NOW,
            "updated_at": NOW,
            "last_message_at": None,
            "messages": [],
        }

    async def append_message(self, *, user_id, conversation_id, request):
        if conversation_id == OTHER_CONVERSATION_ID:
            return None
        row = {
            "id": uuid.uuid5(
                uuid.NAMESPACE_URL,
                f"{conversation_id}:{len(self.appended)}:{request.role}",
            ),
            "user_id": user_id,
            "conversation_id": conversation_id,
            "role": request.role,
            "content": request.content,
            "answer_json": request.answer_json,
            "confidence": request.confidence,
            "needs_human_review": request.needs_human_review,
            "created_at": NOW,
        }
        self.appended.append(row)
        return row


async def _fake_resolve_chat(request: ChatRequest) -> ChatResponse:
    return ChatResponse(
        answer=f"Answer for {request.conversation_id}.",
        confidence=0.87,
        tool_trace=[{"legacy_conversation_id": request.conversation_id}],
    )


def test_unauthenticated_chat_still_works_and_does_not_persist(monkeypatch):
    repository = FakeConversationRepository()
    monkeypatch.setattr(routes_chat, "_resolve_chat", _fake_resolve_chat)

    response = _run(
        routes_chat.chat(
            ChatRequest(message="Hello", conversation_id="legacy-context"),
            conversation_repository=repository,
        )
    )

    assert response.answer == "Answer for legacy-context."
    assert response.db_conversation_id is None
    assert response.tool_trace[0]["legacy_conversation_id"] == "legacy-context"
    assert repository.created_for == []
    assert repository.appended == []


def test_unauthenticated_http_chat_response_omits_new_null_field(monkeypatch):
    monkeypatch.setattr(routes_chat, "_resolve_chat", _fake_resolve_chat)
    app = FastAPI()
    app.include_router(routes_chat.router)

    async def request():
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.post(
                "/chat",
                json={"message": "Hello", "conversation_id": "legacy-context"},
            )

    response = _run(request())

    assert response.status_code == 200
    assert response.json()["answer"] == "Answer for legacy-context."
    assert "db_conversation_id" not in response.json()


def test_chat_rejects_malformed_optional_authorization_before_model_call(monkeypatch):
    async def fail_if_called(request):
        raise AssertionError("Model path must not run for malformed auth")

    monkeypatch.setattr(routes_chat, "_resolve_chat", fail_if_called)
    app = FastAPI()
    app.include_router(routes_chat.router)

    async def request():
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.post(
                "/chat",
                json={"message": "Hello"},
                headers={"Authorization": "Basic nope"},
            )

    response = _run(request())

    assert response.status_code == 401


def test_authenticated_chat_creates_conversation_and_appends_messages(monkeypatch):
    repository = FakeConversationRepository()
    monkeypatch.setattr(routes_chat, "_resolve_chat", _fake_resolve_chat)

    response = _run(
        routes_chat.chat(
            ChatRequest(message="When is add/drop?", conversation_id="legacy-context"),
            current_user=_current_user(),
            conversation_repository=repository,
        )
    )

    assert response.db_conversation_id == NEW_CONVERSATION_ID
    assert repository.created_for == [USER_ID]
    assert [message["role"] for message in repository.appended] == ["user", "assistant"]
    assert repository.appended[0]["content"] == "When is add/drop?"
    assert repository.appended[1]["content"] == "Answer for legacy-context."
    assert repository.appended[1]["answer_json"]["db_conversation_id"] == str(
        NEW_CONVERSATION_ID
    )


def test_authenticated_chat_appends_to_existing_db_conversation(monkeypatch):
    repository = FakeConversationRepository()
    monkeypatch.setattr(routes_chat, "_resolve_chat", _fake_resolve_chat)

    response = _run(
        routes_chat.chat(
            ChatRequest(
                message="Continue this chat",
                conversation_id="legacy-context",
                db_conversation_id=EXISTING_CONVERSATION_ID,
            ),
            current_user=_current_user(),
            conversation_repository=repository,
        )
    )

    assert response.db_conversation_id == EXISTING_CONVERSATION_ID
    assert repository.created_for == []
    assert {message["conversation_id"] for message in repository.appended} == {
        EXISTING_CONVERSATION_ID
    }
    assert [message["role"] for message in repository.appended] == ["user", "assistant"]


def test_cross_user_db_conversation_id_is_rejected_before_model_call(monkeypatch):
    repository = FakeConversationRepository()

    async def fail_if_called(request):
        raise AssertionError("Model path must not run for unauthorized conversation access")

    monkeypatch.setattr(routes_chat, "_resolve_chat", fail_if_called)

    with pytest.raises(HTTPException) as error:
        _run(
            routes_chat.chat(
                ChatRequest(
                    message="Try another user's conversation",
                    db_conversation_id=OTHER_CONVERSATION_ID,
                ),
                current_user=_current_user(),
                conversation_repository=repository,
            )
        )

    assert error.value.status_code == 404
    assert repository.created_for == []
    assert repository.appended == []


def test_chat_still_succeeds_when_new_conversation_persistence_fails(monkeypatch):
    repository = FakeConversationRepository(fail_create=True)
    monkeypatch.setattr(routes_chat, "_resolve_chat", _fake_resolve_chat)

    response = _run(
        routes_chat.chat(
            ChatRequest(message="Hello", conversation_id="legacy-context"),
            current_user=_current_user(),
            conversation_repository=repository,
        )
    )

    assert response.answer == "Answer for legacy-context."
    assert response.db_conversation_id is None
    assert repository.appended == []


def test_streaming_chat_accumulates_and_saves_final_assistant_message(monkeypatch):
    repository = FakeConversationRepository()

    async def fake_stream_response(request):
        return ChatResponse(answer="Streaming answer.", confidence=0.92)

    monkeypatch.setattr(routes_chat, "_resolve_chat", fake_stream_response)
    monkeypatch.setattr(routes_chat, "_answer_chunks", lambda answer: ["Streaming ", "answer."])

    async def request():
        response = await routes_chat.chat_stream(
            ChatRequest(message="Stream this", conversation_id="legacy-stream"),
            current_user=_current_user(),
            conversation_repository=repository,
        )
        chunks = []
        async for chunk in response.body_iterator:
            chunks.append(chunk.decode() if isinstance(chunk, bytes) else chunk)
        return "".join(chunks)

    body = _run(request())

    assert [message["role"] for message in repository.appended] == ["user", "assistant"]
    assert repository.appended[0]["content"] == "Stream this"
    assert repository.appended[1]["content"] == "Streaming answer."
    assert f'"db_conversation_id": "{NEW_CONVERSATION_ID}"' in body
    assert "event: done" in body
