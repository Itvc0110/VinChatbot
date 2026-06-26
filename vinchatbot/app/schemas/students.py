from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class StudentInstituteResponse(BaseModel):
    id: uuid.UUID
    code: str
    name_vi: str
    name_en: str


class AcademicSummaryResponse(BaseModel):
    gpa: Decimal | None = None
    credits_earned: int
    credits_required: int
    current_semester: str | None = None
    academic_status: str
    updated_at: datetime | None = None


class StudentProfileResponse(BaseModel):
    id: uuid.UUID
    student_id: str
    program: str | None = None
    major: str | None = None
    cohort: int | None = None
    academic_year: int | None = None
    student_status: str
    preferred_language: str
    advisor_name: str | None = None
    advisor_email: str | None = None
    ai_personalization_enabled: bool
    institute: StudentInstituteResponse
    academic_summary: AcademicSummaryResponse | None = None


class CourseResponse(BaseModel):
    id: uuid.UUID
    course_code: str
    course_title: str
    credits: int
    semester: str | None = None
    academic_year: str | None = None
    instructor: str | None = None
    institute: StudentInstituteResponse | None = None


class ScheduleItemResponse(BaseModel):
    id: uuid.UUID
    course_id: uuid.UUID | None = None
    course_code: str | None = None
    course_title: str | None = None
    title: str
    schedule_type: str
    start_time: datetime
    end_time: datetime
    location: str | None = None
    building: str | None = None
    room: str | None = None
    instructor: str | None = None
    recurrence_rule: str | None = None


class DeadlineResponse(BaseModel):
    id: uuid.UUID
    course_id: uuid.UUID | None = None
    course_code: str | None = None
    course_title: str | None = None
    title: str
    kind: str | None = None
    due_at: datetime
    source_title: str | None = None
    source_url: str | None = None


class NotificationResponse(BaseModel):
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
    created_at: datetime
    updated_at: datetime
    is_read: bool = False
    important: bool = False
    archived: bool = False


class SuggestedQuestionResponse(BaseModel):
    id: uuid.UUID
    question_text: str
    source_type: str
    source_id: uuid.UUID | None = None
    notification_id: uuid.UUID | None = None
    topic: str | None = None
    intent: str | None = None
    category: str | None = None
    trigger_phase: str | None = None
    institute_id: uuid.UUID | None = None
    institute_code: str | None = None
    course_id: uuid.UUID | None = None
    course_code: str | None = None
    cohort: int | None = None
    score: Decimal
    priority: int
    created_by_ai: bool
    approved_by_admin: bool
    is_active: bool
    valid_from: datetime | None = None
    valid_until: datetime | None = None


class SuggestedQuestionGroupsResponse(BaseModel):
    for_you: list[SuggestedQuestionResponse] = Field(default_factory=list)
    trending_now: list[SuggestedQuestionResponse] = Field(default_factory=list)
    from_announcements: list[SuggestedQuestionResponse] = Field(default_factory=list)
    from_events: list[SuggestedQuestionResponse] = Field(default_factory=list)
