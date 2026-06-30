"""Academic read-model assembly (Phase 13B).

Pure functions that turn the read-only rows from ``AcademicRepository`` into the student-facing
response models. Calculations follow the Phase 13A rules:

* GPA is per term; CPA is cumulative.
* Weighted grade points: ``SUM(grade_4 * credits) / SUM(credits)``.
* 0-credit courses are excluded from GPA/CPA.
* Failed courses grant no earned credits.
* When a course has retake/improvement attempts, only the ``is_gpa_counted`` row affects CPA.
* ``earned_credits`` counts passed courses only.
* Prerequisite = required course already passed before this term.
* Corequisite = required course passed before, or taken in the same term.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from vinchatbot.app.core.timeutils import VINUNI_TZ
from vinchatbot.app.repositories.academic import enrollment_counts_for_gpa, is_failing_grade
from vinchatbot.app.schemas.academic import (
    AcademicCourseResponse,
    AcademicFacultyResponse,
    AcademicOverviewResponse,
    AcademicProfileResponse,
    AcademicProgramResponse,
    AcademicProgressSummary,
    AcademicTermResponse,
    CourseEligibilityResponse,
    CurriculumProgressCourseResponse,
    CurriculumProgressResponse,
    EligibleCourseResponse,
    RequisiteExplanationResponse,
    ScheduleEventResponse,
    StudentCourseEnrollmentResponse,
    TranscriptResponse,
    TranscriptSummaryResponse,
    TranscriptTermGroupResponse,
)

_TWO_PLACES = Decimal("0.01")
# Enrollment statuses that mean "actively taking this course this term" (not yet completed).
ACTIVE_ENROLLMENT_STATUSES = {"planned", "enrolled", "retaking", "improvement"}
# Below this 4-point grade a passed course is still improvable (retake to raise CPA).
IMPROVEMENT_GRADE_CEILING = Decimal("4.0")


def _round2(value: Decimal) -> Decimal:
    return value.quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)


def _gpa_from_entries(entries: list[tuple[Decimal, int]]) -> Decimal | None:
    total_credits = sum(credits for _, credits in entries)
    if total_credits <= 0:
        return None
    weighted = sum(grade * credits for grade, credits in entries)
    return _round2(Decimal(weighted) / Decimal(total_credits))


def _counted_entries(enrollments: list[dict[str, Any]]) -> list[tuple[Decimal, int]]:
    entries: list[tuple[Decimal, int]] = []
    for enrollment in enrollments:
        grade_4 = enrollment.get("grade_4")
        if grade_4 is None:
            continue
        if enrollment_counts_for_gpa(
            credits=enrollment["credits"],
            status=enrollment["status"],
            is_gpa_counted=enrollment["is_gpa_counted"],
        ):
            entries.append((Decimal(grade_4), int(enrollment["credits"])))
    return entries


def compute_term_gpa(enrollments: list[dict[str, Any]]) -> Decimal | None:
    """Weighted GPA over the GPA-counted enrollments of a single term."""
    return _gpa_from_entries(_counted_entries(enrollments))


def compute_cpa(enrollments: list[dict[str, Any]]) -> Decimal | None:
    """Cumulative weighted CPA across all GPA-counted enrollments.

    The ``is_gpa_counted`` partial unique index guarantees at most one counted attempt per course,
    so summing counted rows never double-counts a retaken course.
    """
    return _gpa_from_entries(_counted_entries(enrollments))


def compute_earned_credits(enrollments: list[dict[str, Any]]) -> int:
    """Total credits from passed courses, counting each course at most once."""
    passed: dict[uuid.UUID, int] = {}
    for enrollment in enrollments:
        if enrollment.get("passed"):
            passed[enrollment["course_id"]] = int(enrollment["credits"])
    return sum(passed.values())


def _passed_course_ids(enrollments: list[dict[str, Any]]) -> set[uuid.UUID]:
    return {e["course_id"] for e in enrollments if e.get("passed")}


def _is_failed_attempt(enrollment: dict[str, Any]) -> bool:
    if enrollment.get("passed"):
        return False
    if enrollment.get("status") == "failed":
        return True
    return is_failing_grade(enrollment.get("grade_10"), enrollment.get("grade_4"))


def compute_failed_course_ids(enrollments: list[dict[str, Any]]) -> set[uuid.UUID]:
    """Courses with a failing attempt the student has neither since passed nor is now retaking.

    A failed course that is currently being retaken counts as in-progress, not failed, so the
    overview and curriculum surfaces classify it the same way.
    """
    passed = _passed_course_ids(enrollments)
    active = {e["course_id"] for e in enrollments if e["status"] in ACTIVE_ENROLLMENT_STATUSES}
    failed: set[uuid.UUID] = set()
    for enrollment in enrollments:
        course_id = enrollment["course_id"]
        if course_id in passed or course_id in active:
            continue
        if _is_failed_attempt(enrollment):
            failed.add(course_id)
    return failed


# --- model builders -------------------------------------------------------------------------


def _course_model(row: dict[str, Any]) -> AcademicCourseResponse:
    return AcademicCourseResponse(
        id=row["course_id"],
        code=row["course_code"],
        name=row["course_name"],
        name_vi=row.get("course_name_vi") or row.get("name_vi"),
        credits=row["credits"],
        instructor_name=row.get("instructor_name"),
        course_level=row.get("course_level"),
        department_code=row.get("department_code"),
        is_general_education=bool(row.get("is_general_education", False)),
        description=row.get("description"),
    )


def _term_model(row: dict[str, Any]) -> AcademicTermResponse:
    return AcademicTermResponse(
        id=row["term_id"],
        code=row["term_code"],
        name=row["term_name"],
        start_date=row["start_date"],
        end_date=row["end_date"],
        academic_year=row["academic_year"],
        term_order=row["term_order"],
    )


def term_model_from_row(row: dict[str, Any]) -> AcademicTermResponse:
    """Build a term model from a standalone academic_terms row (id/code/name/...)."""
    return AcademicTermResponse(
        id=row["id"],
        code=row["code"],
        name=row["name"],
        start_date=row["start_date"],
        end_date=row["end_date"],
        academic_year=row["academic_year"],
        term_order=row["term_order"],
    )


def profile_model(profile: dict[str, Any]) -> AcademicProfileResponse:
    faculty = None
    if profile.get("faculty_id") is not None:
        faculty = AcademicFacultyResponse(
            id=profile["faculty_id"],
            code=profile["faculty_code"],
            name=profile["faculty_name"],
        )
    program = _program_model(profile)
    return AcademicProfileResponse(
        id=profile["id"],
        student_code=profile.get("student_code"),
        full_name=profile.get("full_name"),
        current_year=profile.get("current_year"),
        cohort_year=profile.get("cohort_year"),
        status=profile.get("status"),
        faculty=faculty,
        program=program,
    )


def _program_model(profile: dict[str, Any]) -> AcademicProgramResponse | None:
    if profile.get("program_id") is None:
        return None
    return AcademicProgramResponse(
        id=profile["program_id"],
        faculty_id=profile["faculty_id"],
        code=profile["program_code"],
        name=profile["program_name"],
        degree_level=profile["program_degree_level"],
        curriculum_year=profile["program_curriculum_year"],
        total_required_credits=profile["program_total_required_credits"],
    )


def _enrollment_model(row: dict[str, Any]) -> StudentCourseEnrollmentResponse:
    return StudentCourseEnrollmentResponse(
        id=row["id"],
        student_id=row["student_id"],
        course=_course_model(row),
        term=_term_model(row),
        section_id=row.get("section_id"),
        status=row["status"],
        attempt_no=row["attempt_no"],
        is_improvement=row["is_improvement"],
        retake_of_enrollment_id=row.get("retake_of_enrollment_id"),
        grade_10=row.get("grade_10"),
        grade_4=row.get("grade_4"),
        letter_grade=row.get("letter_grade"),
        passed=row["passed"],
        earned_credits=row["earned_credits"],
        is_gpa_counted=row["is_gpa_counted"],
        completed_at=row.get("completed_at"),
    )


def schedule_event_model(row: dict[str, Any]) -> ScheduleEventResponse:
    return ScheduleEventResponse(
        id=row["id"],
        course_code=row["course_code"],
        course_name=row["course_name"],
        course_name_vi=row.get("course_name_vi"),
        section_code=row.get("section_code"),
        instructor_name=row.get("instructor_name"),
        meeting_type=row["meeting_type"],
        title=row["title"],
        start_at=row["start_at"],
        end_at=row["end_at"],
        room_name=row.get("room_name"),
        building=row.get("building"),
        note=row.get("note"),
    )


# --- progress / required-course accounting --------------------------------------------------


def _required_credits(program: dict[str, Any] | None) -> int:
    if not program or program.get("program_total_required_credits") is None:
        return 0
    return int(program["program_total_required_credits"])


def _progress_summary(
    *,
    earned_credits: int,
    required_credits: int,
    completed_required: int,
    remaining_required: int,
) -> AcademicProgressSummary:
    if required_credits > 0:
        percent = _round2(Decimal(earned_credits) / Decimal(required_credits) * Decimal(100))
    else:
        percent = Decimal("0.00")
    return AcademicProgressSummary(
        earned_credits=earned_credits,
        required_credits=required_credits,
        completed_required_courses=completed_required,
        remaining_required_courses=remaining_required,
        progress_percent=percent,
    )


def _curriculum_status(
    course_id: uuid.UUID,
    *,
    passed: set[uuid.UUID],
    failed: set[uuid.UUID],
    active: set[uuid.UUID],
) -> str:
    if course_id in passed:
        return "completed"
    if course_id in active:
        return "in_progress"
    if course_id in failed:
        return "failed"
    return "remaining"


# --- public builders ------------------------------------------------------------------------


def build_transcript(student_id: uuid.UUID, enrollments: list[dict[str, Any]]) -> TranscriptResponse:
    # Preserve repository ordering (term start_date, course_code, attempt_no) while grouping.
    groups: list[dict[str, Any]] = []
    index: dict[uuid.UUID, dict[str, Any]] = {}
    for row in enrollments:
        term_id = row["term_id"]
        group = index.get(term_id)
        if group is None:
            group = {"row": row, "enrollments": []}
            index[term_id] = group
            groups.append(group)
        group["enrollments"].append(row)

    term_groups: list[TranscriptTermGroupResponse] = []
    cumulative_so_far: list[dict[str, Any]] = []
    for group in groups:
        cumulative_so_far.extend(group["enrollments"])
        term_groups.append(
            TranscriptTermGroupResponse(
                term=_term_model(group["row"]),
                enrollments=[_enrollment_model(e) for e in group["enrollments"]],
                term_gpa=compute_term_gpa(group["enrollments"]),
                cumulative_cpa=compute_cpa(list(cumulative_so_far)),
            )
        )

    summary = build_transcript_summary(student_id, enrollments)
    return TranscriptResponse(student_id=student_id, terms=term_groups, summary=summary)


def build_transcript_summary(
    student_id: uuid.UUID, enrollments: list[dict[str, Any]]
) -> TranscriptSummaryResponse:
    counted = [
        e
        for e in enrollments
        if e.get("grade_4") is not None
        and enrollment_counts_for_gpa(
            credits=e["credits"], status=e["status"], is_gpa_counted=e["is_gpa_counted"]
        )
    ]
    attempted_credits = sum(
        int(e["credits"])
        for e in enrollments
        if e["status"] in {"completed", "failed", "improvement", "retaking"}
    )
    return TranscriptSummaryResponse(
        student_id=student_id,
        attempted_credits=attempted_credits,
        earned_credits=compute_earned_credits(enrollments),
        gpa_credits=sum(int(e["credits"]) for e in counted),
        gpa=compute_cpa(enrollments),
        counted_enrollment_ids=[e["id"] for e in counted],
    )


def build_curriculum_progress(
    *,
    program: dict[str, Any] | None,
    curriculum: list[dict[str, Any]],
    enrollments: list[dict[str, Any]],
) -> CurriculumProgressResponse:
    passed = _passed_course_ids(enrollments)
    failed = compute_failed_course_ids(enrollments)
    active = {
        e["course_id"] for e in enrollments if e["status"] in ACTIVE_ENROLLMENT_STATUSES
    }
    # Best GPA-counted (or any) grade per course for display on completed rows.
    grade_by_course: dict[uuid.UUID, Decimal] = {}
    for e in enrollments:
        if e.get("grade_4") is None:
            continue
        course_id = e["course_id"]
        grade = Decimal(e["grade_4"])
        if course_id not in grade_by_course or grade > grade_by_course[course_id]:
            grade_by_course[course_id] = grade

    completed: list[CurriculumProgressCourseResponse] = []
    in_progress: list[CurriculumProgressCourseResponse] = []
    failed_courses: list[CurriculumProgressCourseResponse] = []
    remaining_required: list[CurriculumProgressCourseResponse] = []
    remaining_zero_credit: list[CurriculumProgressCourseResponse] = []

    completed_required = 0
    remaining_required_count = 0

    for row in curriculum:
        course_id = row["course_id"]
        status = _curriculum_status(course_id, passed=passed, failed=failed, active=active)
        item = CurriculumProgressCourseResponse(
            course=_course_model(row),
            category=row["category"],
            is_required=row["is_required"],
            suggested_year=row.get("suggested_year"),
            suggested_term=row.get("suggested_term"),
            status=status,
            grade_4=grade_by_course.get(course_id) if status == "completed" else None,
        )

        if row["is_required"]:
            if status == "completed":
                completed_required += 1
            else:
                remaining_required_count += 1

        if status == "completed":
            completed.append(item)
        elif status == "in_progress":
            in_progress.append(item)
        elif status == "failed":
            failed_courses.append(item)
        else:  # remaining
            if int(row["credits"]) == 0:
                # 0-credit requirements (e.g. PE) are tracked in their own bucket.
                remaining_zero_credit.append(item)
            elif row["is_required"]:
                remaining_required.append(item)
            # Remaining non-required electives are intentionally left out of both buckets.

    summary = _progress_summary(
        earned_credits=compute_earned_credits(enrollments),
        required_credits=_required_credits(program),
        completed_required=completed_required,
        remaining_required=remaining_required_count,
    )
    return CurriculumProgressResponse(
        program=_program_model(program) if program else None,
        completed=completed,
        in_progress=in_progress,
        failed=failed_courses,
        remaining_required=remaining_required,
        remaining_zero_credit=remaining_zero_credit,
        summary=summary,
    )


def _requisite_reason(record: dict[str, Any]) -> str:
    code = record["required_course_code"]
    name = record["required_course_name"]
    min_grade = record.get("min_grade_4")
    grade_clause = f" with at least grade {min_grade} (4-point)" if min_grade else ""
    if record["requisite_type"] == "prerequisite":
        if record["satisfied"]:
            return f"Prerequisite {code} ({name}) is completed."
        return f"Requires prerequisite {code} ({name}){grade_clause} passed before this term."
    if record["satisfied"]:
        return f"Corequisite {code} ({name}) is completed or taken this term."
    return f"Requires corequisite {code} ({name}) passed earlier or taken in the same term."


def build_course_eligibility(
    *,
    term: dict[str, Any] | None,
    curriculum: list[dict[str, Any]],
    enrollments: list[dict[str, Any]],
    requisites_by_course: dict[uuid.UUID, list[dict[str, Any]]],
) -> CourseEligibilityResponse:
    passed = _passed_course_ids(enrollments)
    failed = compute_failed_course_ids(enrollments)
    active_by_course = {
        e["course_id"] for e in enrollments if e["status"] in ACTIVE_ENROLLMENT_STATUSES
    }
    best_grade: dict[uuid.UUID, Decimal] = {}
    for e in enrollments:
        if e.get("grade_4") is None:
            continue
        course_id = e["course_id"]
        grade = Decimal(e["grade_4"])
        if course_id not in best_grade or grade > best_grade[course_id]:
            best_grade[course_id] = grade

    eligible: list[EligibleCourseResponse] = []
    blocked: list[EligibleCourseResponse] = []

    for row in curriculum:
        course_id = row["course_id"]
        currently_enrolled = course_id in active_by_course
        already_completed = course_id in passed
        # Skip courses being taken right now, and completed courses that cannot be improved.
        if currently_enrolled:
            continue
        can_retake_or_improve = course_id in failed or (
            already_completed and best_grade.get(course_id, IMPROVEMENT_GRADE_CEILING) < IMPROVEMENT_GRADE_CEILING
        )
        if already_completed and not can_retake_or_improve:
            continue

        requisites = requisites_by_course.get(course_id, [])
        prerequisites = [r for r in requisites if r["requisite_type"] == "prerequisite"]
        corequisites = [r for r in requisites if r["requisite_type"] == "corequisite"]
        unmet = [r for r in requisites if not r["satisfied"]]

        prereq_models = [
            RequisiteExplanationResponse(
                requisite_type="prerequisite",
                required_course=AcademicCourseResponse(
                    id=r["required_course_id"],
                    code=r["required_course_code"],
                    name=r["required_course_name"],
                    name_vi=r.get("required_course_name_vi"),
                    credits=r.get("required_course_credits", 0),
                ),
                min_grade_4=r.get("min_grade_4"),
                satisfied=r["satisfied"],
                reason=_requisite_reason(r),
            )
            for r in prerequisites
        ]
        coreq_models = [
            RequisiteExplanationResponse(
                requisite_type="corequisite",
                required_course=AcademicCourseResponse(
                    id=r["required_course_id"],
                    code=r["required_course_code"],
                    name=r["required_course_name"],
                    name_vi=r.get("required_course_name_vi"),
                    credits=r.get("required_course_credits", 0),
                ),
                min_grade_4=r.get("min_grade_4"),
                satisfied=r["satisfied"],
                reason=_requisite_reason(r),
            )
            for r in corequisites
        ]

        blocking_reasons = [_requisite_reason(r) for r in unmet]
        is_eligible = not blocking_reasons
        entry = EligibleCourseResponse(
            course=_course_model(row),
            category=row.get("category"),
            is_required=bool(row.get("is_required", True)),
            eligible=is_eligible,
            already_completed=already_completed,
            currently_enrolled=currently_enrolled,
            can_retake_or_improve=can_retake_or_improve,
            blocking_reasons=blocking_reasons,
            prerequisites=prereq_models,
            corequisites=coreq_models,
        )
        if is_eligible:
            eligible.append(entry)
        else:
            blocked.append(entry)

    return CourseEligibilityResponse(
        term=term_model_from_row(term) if term else None,
        eligible=eligible,
        blocked=blocked,
    )


def build_overview(
    *,
    profile: dict[str, Any],
    current_term: dict[str, Any] | None,
    enrollments: list[dict[str, Any]],
    curriculum: list[dict[str, Any]],
    upcoming_meetings: list[dict[str, Any]],
) -> AcademicOverviewResponse:
    program = profile if profile.get("program_id") else None
    current_term_id = current_term["id"] if current_term else None
    current_term_enrollments = [
        e for e in enrollments if current_term_id is not None and e["term_id"] == current_term_id
    ]

    # Current GPA = the current term's GPA, or — when the current term is still in progress and has
    # no graded GPA-counted rows yet — the most recent term that does have a computable GPA.
    current_gpa = compute_term_gpa(current_term_enrollments)
    if current_gpa is None:
        ordered_term_ids: list[Any] = []
        by_term: dict[Any, list[dict[str, Any]]] = {}
        for enrollment in enrollments:
            term_id = enrollment["term_id"]
            if term_id not in by_term:
                by_term[term_id] = []
                ordered_term_ids.append(term_id)
            by_term[term_id].append(enrollment)
        for term_id in ordered_term_ids:  # chronological (repo orders by term start_date)
            term_gpa = compute_term_gpa(by_term[term_id])
            if term_gpa is not None:
                current_gpa = term_gpa

    # Currently enrolled (active) distinct courses in the current term.
    seen: set[uuid.UUID] = set()
    enrolled_courses: list[AcademicCourseResponse] = []
    for e in current_term_enrollments:
        if e["status"] in ACTIVE_ENROLLMENT_STATUSES and e["course_id"] not in seen:
            seen.add(e["course_id"])
            enrolled_courses.append(_course_model(e))

    failed_ids = compute_failed_course_ids(enrollments)
    failed_courses: list[AcademicCourseResponse] = []
    seen_failed: set[uuid.UUID] = set()
    for e in enrollments:
        if e["course_id"] in failed_ids and e["course_id"] not in seen_failed:
            seen_failed.add(e["course_id"])
            failed_courses.append(_course_model(e))

    progress = build_curriculum_progress(
        program=program, curriculum=curriculum, enrollments=enrollments
    )

    return AcademicOverviewResponse(
        profile=profile_model(profile),
        current_term=term_model_from_row(current_term) if current_term else None,
        current_gpa=current_gpa,
        cumulative_cpa=compute_cpa(enrollments),
        earned_credits=progress.summary.earned_credits,
        required_credits=progress.summary.required_credits,
        failed_courses=failed_courses,
        enrolled_courses=enrolled_courses,
        upcoming_meetings=[schedule_event_model(m) for m in upcoming_meetings],
        summary=progress.summary,
    )


def month_window(year: int, month: int) -> tuple[datetime, datetime]:
    """[start, end) window covering a calendar month in VinUni local time.

    VinUni schedules are stored as ``timestamptz`` in +07; anchoring the window to VinUni time makes
    "month=2026-06" mean the June calendar month as a student in Hanoi would read it.
    """
    start = datetime(year, month, 1, tzinfo=VINUNI_TZ)
    if month == 12:
        end = datetime(year + 1, 1, 1, tzinfo=VINUNI_TZ)
    else:
        end = datetime(year, month + 1, 1, tzinfo=VINUNI_TZ)
    return start, end
