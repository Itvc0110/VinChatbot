from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

MESSAGE_ROLES = {"user", "assistant", "system", "tool"}


class MessageResponse(BaseModel):
    id: uuid.UUID
    conversation_id: uuid.UUID
    role: str
    content: str
    answer_json: dict[str, Any] | None = None
    intent: str | None = None
    topic: str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    needs_human_review: bool = False
    created_at: datetime


class ConversationSummaryResponse(BaseModel):
    id: uuid.UUID
    title: str
    title_manual: bool
    topic: str | None = None
    created_at: datetime
    updated_at: datetime
    last_message_at: datetime | None = None


class ConversationDetailResponse(ConversationSummaryResponse):
    messages: list[MessageResponse] = Field(default_factory=list)


class CreateConversationRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    topic: str | None = Field(default=None, max_length=120)
    initial_message: str | None = Field(default=None, min_length=1, max_length=4000)


class UpdateConversationRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    topic: str | None = Field(default=None, max_length=120)
    title_manual: bool | None = None


class RenameConversationRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)


class AppendMessageRequest(BaseModel):
    role: str
    content: str = Field(min_length=1, max_length=4000)
    answer_json: dict[str, Any] | None = None
    intent: str | None = Field(default=None, max_length=120)
    topic: str | None = Field(default=None, max_length=120)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    needs_human_review: bool = False

    @field_validator("role")
    @classmethod
    def validate_role(cls, value: str) -> str:
        role = value.strip().lower()
        if role not in MESSAGE_ROLES:
            allowed = ", ".join(sorted(MESSAGE_ROLES))
            raise ValueError(f"role must be one of: {allowed}")
        return role


class ConversationDeleteResponse(BaseModel):
    deleted: bool
