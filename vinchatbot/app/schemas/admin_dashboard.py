from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class AdminDashboardScopeResponse(BaseModel):
    kind: str
    institute_id: uuid.UUID | None = None
    institute_code: str | None = None


class AdminDashboardOverviewResponse(BaseModel):
    total_users: int = 0
    total_students: int = 0
    total_institutes: int = 0
    total_tickets: int = 0
    open_tickets: int = 0
    need_admin_response: int = 0
    urgent_tickets: int = 0
    upcoming_deadlines: int = 0
    upcoming_schedules: int = 0
    upcoming_events: int = 0
    published_notifications: int = 0


class AdminDashboardCountResponse(BaseModel):
    key: str
    count: int


class AdminDashboardInstituteCountResponse(BaseModel):
    institute_id: uuid.UUID
    institute_code: str
    institute_name_en: str
    institute_name_vi: str
    student_count: int


class AdminDashboardRecentTicketResponse(BaseModel):
    id: uuid.UUID
    subject: str
    status: str
    priority: str
    student_id: str | None = None
    student_name: str | None = None
    institute_id: uuid.UUID | None = None
    institute_code: str | None = None
    due_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class AdminDashboardUpcomingItemResponse(BaseModel):
    id: uuid.UUID
    item_type: str
    title: str
    starts_at: datetime
    ends_at: datetime | None = None
    course_code: str | None = None
    institute_id: uuid.UUID | None = None
    institute_code: str | None = None
    source_title: str | None = None
    source_url: str | None = None


class AdminDashboardResponse(BaseModel):
    scope: AdminDashboardScopeResponse
    overview: AdminDashboardOverviewResponse
    ticket_counts_by_status: list[AdminDashboardCountResponse] = Field(default_factory=list)
    ticket_counts_by_priority: list[AdminDashboardCountResponse] = Field(default_factory=list)
    student_counts_by_institute: list[AdminDashboardInstituteCountResponse] = Field(
        default_factory=list
    )
    recent_tickets: list[AdminDashboardRecentTicketResponse] = Field(default_factory=list)
    upcoming_items: list[AdminDashboardUpcomingItemResponse] = Field(default_factory=list)
