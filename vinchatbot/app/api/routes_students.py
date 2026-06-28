from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from vinchatbot.app.db.connection import get_app_db_pool
from vinchatbot.app.dependencies.auth import require_roles
from vinchatbot.app.repositories.auth import AuthenticatedUser
from vinchatbot.app.repositories.students import StudentRepository
from vinchatbot.app.schemas.students import (
    CourseResponse,
    DeadlineResponse,
    NotificationMarkAllReadResponse,
    NotificationReadStateResponse,
    NotificationResponse,
    ScheduleItemResponse,
    StudentProfileResponse,
    SuggestedQuestionGroupsResponse,
)

router = APIRouter(tags=["students"])
StudentUser = Annotated[AuthenticatedUser, Depends(require_roles("student"))]


def get_student_repository() -> StudentRepository:
    pool = get_app_db_pool()
    if pool is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="App database is not configured.",
        )
    return StudentRepository(pool)


async def current_student_profile(
    current_user: AuthenticatedUser,
    repository: StudentRepository,
) -> dict:
    profile = await repository.get_current_student_profile(current_user.id)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student profile not found.",
        )
    return profile


@router.get("/students/me", response_model=StudentProfileResponse)
async def student_me(
    current_user: StudentUser,
    repository: Annotated[StudentRepository, Depends(get_student_repository)],
) -> StudentProfileResponse:
    profile = await current_student_profile(current_user, repository)
    return StudentProfileResponse(**profile)


@router.get("/students/me/courses", response_model=list[CourseResponse])
async def student_courses(
    current_user: StudentUser,
    repository: Annotated[StudentRepository, Depends(get_student_repository)],
) -> list[CourseResponse]:
    profile = await current_student_profile(current_user, repository)
    courses = await repository.get_courses(profile["id"])
    return [CourseResponse(**course) for course in courses]


@router.get("/students/me/schedule", response_model=list[ScheduleItemResponse])
async def student_schedule(
    current_user: StudentUser,
    repository: Annotated[StudentRepository, Depends(get_student_repository)],
    upcoming_only: Annotated[bool, Query()] = True,
) -> list[ScheduleItemResponse]:
    profile = await current_student_profile(current_user, repository)
    schedule = await repository.get_schedule(profile["id"], upcoming_only=upcoming_only)
    return [ScheduleItemResponse(**item) for item in schedule]


@router.get("/students/me/deadlines", response_model=list[DeadlineResponse])
async def student_deadlines(
    current_user: StudentUser,
    repository: Annotated[StudentRepository, Depends(get_student_repository)],
    upcoming_only: Annotated[bool, Query()] = True,
) -> list[DeadlineResponse]:
    profile = await current_student_profile(current_user, repository)
    deadlines = await repository.get_deadlines(profile["id"], upcoming_only=upcoming_only)
    return [DeadlineResponse(**deadline) for deadline in deadlines]


@router.get("/students/me/notifications", response_model=list[NotificationResponse])
async def student_notifications(
    current_user: StudentUser,
    repository: Annotated[StudentRepository, Depends(get_student_repository)],
    lang: Annotated[str, Query()] = "vi",
) -> list[NotificationResponse]:
    profile = await current_student_profile(current_user, repository)
    notifications = await repository.get_notifications(
        user_id=current_user.id,
        profile=profile,
        lang=lang,
    )
    return [NotificationResponse(**notification) for notification in notifications]


@router.post(
    "/students/me/notifications/mark-all-read",
    response_model=NotificationMarkAllReadResponse,
)
async def mark_all_student_notifications_read(
    current_user: StudentUser,
    repository: Annotated[StudentRepository, Depends(get_student_repository)],
) -> NotificationMarkAllReadResponse:
    profile = await current_student_profile(current_user, repository)
    updated_count = await repository.mark_all_notifications_read(
        user_id=current_user.id,
        profile=profile,
    )
    return NotificationMarkAllReadResponse(updated_count=updated_count)


@router.post(
    "/students/me/notifications/{notification_id}/read",
    response_model=NotificationReadStateResponse,
)
async def mark_student_notification_read(
    notification_id: uuid.UUID,
    current_user: StudentUser,
    repository: Annotated[StudentRepository, Depends(get_student_repository)],
) -> NotificationReadStateResponse:
    profile = await current_student_profile(current_user, repository)
    state = await repository.mark_notification_read(
        notification_id=notification_id,
        user_id=current_user.id,
        profile=profile,
    )
    if state is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found.",
        )
    return NotificationReadStateResponse(**state)


@router.post(
    "/students/me/notifications/{notification_id}/unread",
    response_model=NotificationReadStateResponse,
)
async def mark_student_notification_unread(
    notification_id: uuid.UUID,
    current_user: StudentUser,
    repository: Annotated[StudentRepository, Depends(get_student_repository)],
) -> NotificationReadStateResponse:
    profile = await current_student_profile(current_user, repository)
    state = await repository.mark_notification_unread(
        notification_id=notification_id,
        user_id=current_user.id,
        profile=profile,
    )
    if state is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found.",
        )
    return NotificationReadStateResponse(**state)


@router.get("/suggestions/me", response_model=SuggestedQuestionGroupsResponse)
async def student_suggestions(
    current_user: StudentUser,
    repository: Annotated[StudentRepository, Depends(get_student_repository)],
    lang: Annotated[str, Query()] = "vi",
) -> SuggestedQuestionGroupsResponse:
    profile = await current_student_profile(current_user, repository)
    suggestions = await repository.get_suggestions(
        user_id=current_user.id, profile=profile, lang=lang
    )
    return group_suggestions(suggestions)


def group_suggestions(suggestions: list[dict]) -> SuggestedQuestionGroupsResponse:
    grouped: dict[str, list[dict]] = {
        "for_you": [],
        "trending_now": [],
        "from_announcements": [],
        "from_events": [],
    }

    for suggestion in suggestions:
        source_type = str(suggestion.get("source_type") or "")
        category = str(suggestion.get("category") or "")
        trigger_phase = str(suggestion.get("trigger_phase") or "")

        if source_type == "trend":
            bucket = "trending_now"
        elif source_type == "notification":
            bucket = "from_announcements"
        elif source_type == "event" or category == "event" or trigger_phase == "upcoming_event":
            bucket = "from_events"
        elif source_type in {"schedule", "deadline", "ticket", "personal"} or category in {
            "schedule_context",
            "deadline_context",
            "ticket",
        }:
            bucket = "for_you"
        else:
            bucket = "for_you"

        grouped[bucket].append(suggestion)

    return SuggestedQuestionGroupsResponse(**grouped)
