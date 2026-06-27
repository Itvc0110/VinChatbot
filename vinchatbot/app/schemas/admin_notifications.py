from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator, model_validator

NOTIFICATION_TYPES = {
    "announcement",
    "deadline",
    "event",
    "academic",
    "schedule",
    "student_services",
    "system",
    "emergency",
    "forum",
}
NOTIFICATION_PRIORITIES = {"low", "medium", "high", "urgent"}
NOTIFICATION_STATUSES = {"draft", "scheduled", "published", "archived"}
NOTIFICATION_TARGET_SCOPES = {"all", "institute", "cohort"}


class AdminNotificationResponse(BaseModel):
    id: uuid.UUID
    type: str
    title: str
    message: str
    priority: str
    status: str
    target_scope: str
    institute_id: uuid.UUID | None = None
    institute_code: str | None = None
    course_id: uuid.UUID | None = None
    course_code: str | None = None
    cohort: int | None = None
    deadline: datetime | None = None
    event_date: datetime | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    source_title: str | None = None
    source_url: str | None = None
    created_by: uuid.UUID | None = None
    created_by_email: str | None = None
    created_by_name: str | None = None
    created_at: datetime
    updated_at: datetime


class AdminNotificationTargetResponse(BaseModel):
    id: uuid.UUID
    code: str
    name_vi: str
    name_en: str


class AdminNotificationCreateRequest(BaseModel):
    type: str = Field(default="announcement")
    title: str = Field(min_length=1, max_length=300)
    message: str = Field(min_length=1, max_length=5000)
    priority: str = Field(default="medium")
    status: str = Field(default="draft")
    target_scope: str = Field(default="all")
    institute_id: uuid.UUID | None = None
    cohort: int | None = None
    deadline: datetime | None = None
    event_date: datetime | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    source_title: str | None = Field(default=None, max_length=500)
    source_url: str | None = Field(default=None, max_length=2000)

    @field_validator("title", "message")
    @classmethod
    def validate_nonblank_text(cls, value: str) -> str:
        return validate_nonblank(value)

    @model_validator(mode="after")
    def validate_values(self) -> AdminNotificationCreateRequest:
        validate_notification_values(
            notification_type=self.type,
            priority=self.priority,
            status=self.status,
            target_scope=self.target_scope,
            institute_id=self.institute_id,
            start_date=self.start_date,
            end_date=self.end_date,
        )
        return self


class AdminNotificationUpdateRequest(BaseModel):
    type: str | None = None
    title: str | None = Field(default=None, min_length=1, max_length=300)
    message: str | None = Field(default=None, min_length=1, max_length=5000)
    priority: str | None = None
    target_scope: str | None = None
    institute_id: uuid.UUID | None = None
    cohort: int | None = None
    deadline: datetime | None = None
    event_date: datetime | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    source_title: str | None = Field(default=None, max_length=500)
    source_url: str | None = Field(default=None, max_length=2000)

    @field_validator("title", "message")
    @classmethod
    def validate_optional_nonblank_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return validate_nonblank(value)

    @model_validator(mode="after")
    def validate_values(self) -> AdminNotificationUpdateRequest:
        if self.type is not None and self.type not in NOTIFICATION_TYPES:
            raise ValueError("Invalid notification type.")
        if self.priority is not None and self.priority not in NOTIFICATION_PRIORITIES:
            raise ValueError("Invalid notification priority.")
        if self.target_scope is not None:
            if self.target_scope not in NOTIFICATION_TARGET_SCOPES:
                raise ValueError("Invalid notification target scope.")
            if self.target_scope == "institute" and self.institute_id is None:
                raise ValueError("Institute-targeted notifications require institute_id.")
        if self.start_date is not None and self.end_date is not None and self.end_date < self.start_date:
            raise ValueError("end_date must be greater than or equal to start_date.")
        return self


class AdminNotificationScheduleRequest(BaseModel):
    publish_at: datetime
    end_date: datetime | None = None

    @model_validator(mode="after")
    def validate_window(self) -> AdminNotificationScheduleRequest:
        if self.end_date is not None and self.end_date < self.publish_at:
            raise ValueError("end_date must be greater than or equal to publish_at.")
        return self


def validate_notification_values(
    *,
    notification_type: str,
    priority: str,
    status: str,
    target_scope: str,
    institute_id: uuid.UUID | None,
    start_date: datetime | None,
    end_date: datetime | None,
) -> None:
    if notification_type not in NOTIFICATION_TYPES:
        raise ValueError("Invalid notification type.")
    if priority not in NOTIFICATION_PRIORITIES:
        raise ValueError("Invalid notification priority.")
    if status not in NOTIFICATION_STATUSES:
        raise ValueError("Invalid notification status.")
    if status == "scheduled" and start_date is None:
        raise ValueError("Scheduled notifications require start_date.")
    if target_scope not in NOTIFICATION_TARGET_SCOPES:
        raise ValueError("Invalid notification target scope.")
    if target_scope == "institute" and institute_id is None:
        raise ValueError("Institute-targeted notifications require institute_id.")
    if start_date is not None and end_date is not None and end_date < start_date:
        raise ValueError("end_date must be greater than or equal to start_date.")


def validate_nonblank(value: str) -> str:
    stripped = value.strip()
    if not stripped:
        raise ValueError("Text fields must not be blank.")
    return stripped
