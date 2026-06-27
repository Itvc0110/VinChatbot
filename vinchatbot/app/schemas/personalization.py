from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class PersonalizationInstitute(BaseModel):
    id: uuid.UUID
    code: str
    name_vi: str
    name_en: str


class PersonalizationAcademicSummary(BaseModel):
    gpa: Decimal | None = None
    credits_earned: int
    credits_required: int
    current_semester: str | None = None
    academic_status: str


class PersonalizationStudentProfile(BaseModel):
    id: uuid.UUID
    student_id: str
    program: str | None = None
    major: str | None = None
    cohort: int | None = None
    academic_year: int | None = None
    preferred_language: str
    ai_personalization_enabled: bool
    institute: PersonalizationInstitute
    academic_summary: PersonalizationAcademicSummary | None = None


class PersonalizationCourse(BaseModel):
    id: uuid.UUID
    course_code: str
    course_title: str
    semester: str | None = None
    academic_year: str | None = None
    instructor: str | None = None


class PersonalizationScheduleItem(BaseModel):
    id: uuid.UUID
    title: str
    schedule_type: str
    start_time: datetime
    end_time: datetime
    course_code: str | None = None
    course_title: str | None = None
    location: str | None = None
    room: str | None = None


class PersonalizationDeadline(BaseModel):
    id: uuid.UUID
    title: str
    due_at: datetime
    kind: str | None = None
    course_code: str | None = None
    course_title: str | None = None


class PersonalizationNotification(BaseModel):
    id: uuid.UUID
    type: str
    title: str
    priority: str
    deadline: datetime | None = None
    event_date: datetime | None = None
    source_title: str | None = None
    is_read: bool = False
    important: bool = False


class PersonalizationSuggestion(BaseModel):
    id: uuid.UUID
    question_text: str
    source_type: str
    category: str | None = None
    priority: int


class PersonalizationForumTopic(BaseModel):
    id: uuid.UUID
    title: str
    category_slug: str | None = None
    category_name_en: str | None = None
    is_pinned: bool = False
    last_activity_at: datetime | None = None


class PersonalizationConversation(BaseModel):
    id: uuid.UUID
    title: str
    topic: str | None = None
    updated_at: datetime
    last_message_at: datetime | None = None


class PersonalizationContext(BaseModel):
    profile: PersonalizationStudentProfile
    courses: list[PersonalizationCourse] = Field(default_factory=list)
    schedule: list[PersonalizationScheduleItem] = Field(default_factory=list)
    deadlines: list[PersonalizationDeadline] = Field(default_factory=list)
    notifications: list[PersonalizationNotification] = Field(default_factory=list)
    suggestions: list[PersonalizationSuggestion] = Field(default_factory=list)
    forum_topics: list[PersonalizationForumTopic] = Field(default_factory=list)
    recent_conversations: list[PersonalizationConversation] = Field(default_factory=list)
