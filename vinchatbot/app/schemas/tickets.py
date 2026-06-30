from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

TICKET_STATUSES = {
    "submitted",
    "open",
    "in_progress",
    "waiting_on_student",
    "resolved",
    "closed",
}
TICKET_PRIORITIES = {"low", "medium", "high", "urgent"}

# Categories the student-facing ticket drawer offers (must match the frontend `TicketCategory` set in
# `frontend/lib/portalTypes.ts`). The AI draft suggestion is constrained to these; anything else → "other".
TICKET_CATEGORIES = {"academic", "schedule", "student_services", "technical", "other"}


class TicketMessageResponse(BaseModel):
    id: uuid.UUID
    ticket_id: uuid.UUID
    sender_user_id: uuid.UUID | None = None
    sender_email: str | None = None
    sender_full_name: str | None = None
    author_type: str
    body: str
    created_at: datetime


class TicketStatusHistoryResponse(BaseModel):
    id: uuid.UUID
    old_status: str | None = None
    new_status: str
    changed_by: uuid.UUID | None = None
    changed_by_email: str | None = None
    changed_by_full_name: str | None = None
    changed_at: datetime


class TicketSummaryResponse(BaseModel):
    id: uuid.UUID
    student_profile_id: uuid.UUID
    student_id: str | None = None
    student_name: str | None = None
    institute_id: uuid.UUID | None = None
    institute_code: str | None = None
    subject: str
    body: str
    department: str | None = None
    category: str | None = None
    priority: str
    status: str
    confirmed_by_user: bool
    created_by_ai: bool
    include_chat_context: bool
    source_conversation_id: uuid.UUID | None = None
    origin_question: str | None = None
    assigned_admin_id: uuid.UUID | None = None
    assignee: str | None = None
    submitted_at: datetime | None = None
    due_at: datetime | None = None
    sla_hours: int | None = None
    resolution: str | None = None
    archived: bool
    deleted: bool
    created_at: datetime
    updated_at: datetime


class TicketDetailResponse(TicketSummaryResponse):
    included_context: str | None = None
    messages: list[TicketMessageResponse] = Field(default_factory=list)
    status_history: list[TicketStatusHistoryResponse] = Field(default_factory=list)


class CreateTicketRequest(BaseModel):
    subject: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=5000)
    department: str | None = Field(default=None, max_length=120)
    category: str | None = Field(default=None, max_length=120)
    priority: str = "medium"
    include_chat_context: bool = False
    included_context: str | None = Field(default=None, max_length=4000)
    source_conversation_id: uuid.UUID | None = None
    origin_question: str | None = Field(default=None, max_length=1000)
    # True when the draft was produced by Vinnie's suggestion (the student still reviewed + confirmed in
    # the drawer, so confirmed_by_user stays true). Lets admin see the ticket was AI-drafted.
    created_by_ai: bool = False

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, value: str) -> str:
        priority = value.strip().lower()
        if priority not in TICKET_PRIORITIES:
            allowed = ", ".join(sorted(TICKET_PRIORITIES))
            raise ValueError(f"priority must be one of: {allowed}")
        return priority


class SuggestTicketRequest(BaseModel):
    """Input for the Vinnie ticket-draft suggestion — the conversation the client already has."""

    origin_question: str = Field(min_length=1, max_length=2000)
    answer: str | None = Field(default=None, max_length=8000)
    context: str | None = Field(default=None, max_length=8000)


class SuggestedTicketDraft(BaseModel):
    """A drafted ticket (summary / description / category) for the student to review before sending."""

    subject: str = Field(max_length=200)
    body: str = Field(max_length=5000)
    category: str = Field(default="other", max_length=120)


class AddTicketMessageRequest(BaseModel):
    body: str = Field(min_length=1, max_length=5000)


class AdminUpdateTicketRequest(BaseModel):
    status: str | None = None
    priority: str | None = None
    assigned_admin_id: uuid.UUID | None = None
    resolution: str | None = Field(default=None, max_length=5000)
    archived: bool | None = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str | None) -> str | None:
        if value is None:
            return None
        status = value.strip().lower()
        if status not in TICKET_STATUSES:
            allowed = ", ".join(sorted(TICKET_STATUSES))
            raise ValueError(f"status must be one of: {allowed}")
        return status

    @field_validator("priority")
    @classmethod
    def validate_optional_priority(cls, value: str | None) -> str | None:
        if value is None:
            return None
        priority = value.strip().lower()
        if priority not in TICKET_PRIORITIES:
            allowed = ", ".join(sorted(TICKET_PRIORITIES))
            raise ValueError(f"priority must be one of: {allowed}")
        return priority


class AdminTicketFilters(BaseModel):
    status: str | None = None
    priority: str | None = None
    include_archived: bool = False

    @field_validator("status")
    @classmethod
    def validate_filter_status(cls, value: str | None) -> str | None:
        if value is None:
            return None
        status = value.strip().lower()
        if status not in TICKET_STATUSES:
            allowed = ", ".join(sorted(TICKET_STATUSES))
            raise ValueError(f"status must be one of: {allowed}")
        return status

    @field_validator("priority")
    @classmethod
    def validate_filter_priority(cls, value: str | None) -> str | None:
        if value is None:
            return None
        priority = value.strip().lower()
        if priority not in TICKET_PRIORITIES:
            allowed = ", ".join(sorted(TICKET_PRIORITIES))
            raise ValueError(f"priority must be one of: {allowed}")
        return priority
