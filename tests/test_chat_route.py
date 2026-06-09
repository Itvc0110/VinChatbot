from __future__ import annotations

import asyncio

import pytest
from fastapi import HTTPException

from vinchatbot.app.api import routes_chat
from vinchatbot.app.schemas.chat import ChatRequest


def test_chat_returns_service_unavailable_for_unexpected_provider_error(monkeypatch):
    class FailingService:
        async def chat(self, request):
            raise ValueError("provider failed")

    monkeypatch.setattr(routes_chat, "get_agent_service", lambda: FailingService())

    with pytest.raises(HTTPException) as error:
        asyncio.run(routes_chat.chat(ChatRequest(message="test")))

    assert error.value.status_code == 503
    assert "ValueError" in error.value.detail
