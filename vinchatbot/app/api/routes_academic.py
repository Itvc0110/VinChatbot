from __future__ import annotations

import re
from datetime import timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from vinchatbot.app.core.timeutils import now_in_vietnam
from vinchatbot.app.db.connection import get_app_db_pool
from vinchatbot.app.dependencies.auth import require_roles
from vinchatbot.app.repositories.academic import AcademicRepository
from vinchatbot.app.repositories.auth import AuthenticatedUser
from vinchatbot.app.schemas.academic import (
    AcademicOverviewResponse,
    CourseEligibilityResponse,
    CurriculumProgressResponse,
    ScheduleEventResponse,
    TranscriptResponse,
)
from vinchatbot.app.services import academic as academic_service

router = APIRouter(tags=["academic"])
StudentUser = Annotated[AuthenticatedUser, Depends(require_roles("student"))]

# Window scanned for the overview's "upcoming class meetings" preview.
UPCOMING_MEETINGS_DAYS = 30
UPCOMING_MEETINGS_LIMIT = 8
_MONTH_RE = re.compile(r"^(\d{4})-(\d{2})$")


def get_academic_repository() -> AcademicRepository:
    pool = get_app_db_pool()
    if pool is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="App database is not configured.",
        )
    return AcademicRepository(pool)


async def current_academic_profile(
    current_user: AuthenticatedUser,
    repository: AcademicRepository,
) -> dict[str, Any]:
    """Resolve the academic profile for the authenticated user (current_user.id -> profile).

    Raises 404 when the user has no student profile so /me endpoints never leak other students.
    """
    profile = await repository.get_student_profile_by_user(current_user.id)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student academic profile not found.",
        )
    return profile


async def _curriculum_for_profile(
    repository: AcademicRepository, profile: dict[str, Any]
) -> list[dict[str, Any]]:
    program_id = profile.get("program_id")
    if program_id is None:
        return []
    return await repository.get_curriculum(program_id)


@router.get("/academic/me", response_model=AcademicOverviewResponse)
async def academic_me(
    current_user: StudentUser,
    repository: Annotated[AcademicRepository, Depends(get_academic_repository)],
) -> AcademicOverviewResponse:
    profile = await current_academic_profile(current_user, repository)
    student_id = profile["id"]

    current_term = await repository.get_current_term()
    enrollments = await repository.get_student_transcript(student_id)
    curriculum = await _curriculum_for_profile(repository, profile)

    now = now_in_vietnam()
    upcoming = await repository.get_student_meetings_in_range(
        student_id=student_id,
        start_at=now,
        end_at=now + timedelta(days=UPCOMING_MEETINGS_DAYS),
    )

    return academic_service.build_overview(
        profile=profile,
        current_term=current_term,
        enrollments=enrollments,
        curriculum=curriculum,
        upcoming_meetings=upcoming[:UPCOMING_MEETINGS_LIMIT],
    )


@router.get("/academic/me/transcript", response_model=TranscriptResponse)
async def academic_me_transcript(
    current_user: StudentUser,
    repository: Annotated[AcademicRepository, Depends(get_academic_repository)],
) -> TranscriptResponse:
    profile = await current_academic_profile(current_user, repository)
    enrollments = await repository.get_student_transcript(profile["id"])
    return academic_service.build_transcript(profile["id"], enrollments)


@router.get("/academic/me/curriculum", response_model=CurriculumProgressResponse)
async def academic_me_curriculum(
    current_user: StudentUser,
    repository: Annotated[AcademicRepository, Depends(get_academic_repository)],
) -> CurriculumProgressResponse:
    profile = await current_academic_profile(current_user, repository)
    enrollments = await repository.get_student_transcript(profile["id"])
    curriculum = await _curriculum_for_profile(repository, profile)
    program = profile if profile.get("program_id") else None
    return academic_service.build_curriculum_progress(
        program=program, curriculum=curriculum, enrollments=enrollments
    )


@router.get("/academic/me/courses/eligible", response_model=CourseEligibilityResponse)
async def academic_me_eligible_courses(
    current_user: StudentUser,
    repository: Annotated[AcademicRepository, Depends(get_academic_repository)],
) -> CourseEligibilityResponse:
    profile = await current_academic_profile(current_user, repository)
    student_id = profile["id"]

    current_term = await repository.get_current_term()
    enrollments = await repository.get_student_transcript(student_id)
    curriculum = await _curriculum_for_profile(repository, profile)

    requisites_by_course: dict[Any, list[dict[str, Any]]] = {}
    if current_term is not None and curriculum:
        requisites_by_course = await repository.get_requisite_status_bulk(
            student_id=student_id,
            course_ids=[row["course_id"] for row in curriculum],
            term_id=current_term["id"],
        )

    return academic_service.build_course_eligibility(
        term=current_term,
        curriculum=curriculum,
        enrollments=enrollments,
        requisites_by_course=requisites_by_course,
    )


def _parse_month(month: str) -> tuple[int, int]:
    match = _MONTH_RE.match(month)
    if not match:
        raise HTTPException(
            status_code=422,  # Unprocessable Entity (invalid month param)
            detail="month must be in YYYY-MM format.",
        )
    year, month_value = int(match.group(1)), int(match.group(2))
    if not 1 <= month_value <= 12:
        raise HTTPException(
            status_code=422,  # Unprocessable Entity (invalid month param)
            detail="month must be between 01 and 12.",
        )
    return year, month_value


@router.get("/schedule/me", response_model=list[ScheduleEventResponse])
async def schedule_me(
    current_user: StudentUser,
    repository: Annotated[AcademicRepository, Depends(get_academic_repository)],
    month: Annotated[str, Query(description="Calendar month in YYYY-MM (VinUni local time).")],
) -> list[ScheduleEventResponse]:
    profile = await current_academic_profile(current_user, repository)
    year, month_value = _parse_month(month)
    start_at, end_at = academic_service.month_window(year, month_value)
    meetings = await repository.get_student_meetings_in_range(
        student_id=profile["id"],
        start_at=start_at,
        end_at=end_at,
    )
    return [academic_service.schedule_event_model(meeting) for meeting in meetings]
