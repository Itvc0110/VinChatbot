from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from psycopg_pool import AsyncConnectionPool

PASSING_GRADE_10 = Decimal("4.0")
PASSING_GRADE_4 = Decimal("1.0")
GPA_STATUSES = {"completed", "failed", "improvement"}
SAME_TERM_REQUISITE_STATUSES = {"planned", "enrolled", "completed", "retaking", "improvement"}


def is_failing_grade(grade_10: Decimal | None, grade_4: Decimal | None) -> bool:
    if grade_10 is None and grade_4 is None:
        return False
    return (grade_10 is not None and grade_10 < PASSING_GRADE_10) or (
        grade_4 is not None and grade_4 < PASSING_GRADE_4
    )


def enrollment_counts_for_gpa(*, credits: int, status: str, is_gpa_counted: bool) -> bool:
    return credits > 0 and status in GPA_STATUSES and is_gpa_counted


def requisite_is_satisfied(
    *,
    requisite_type: str,
    required_passed: bool,
    required_same_term: bool,
) -> bool:
    if requisite_type == "prerequisite":
        return required_passed
    if requisite_type == "corequisite":
        return required_passed or required_same_term
    return False


class AcademicRepository:
    """Read helpers for the Phase 13A academic demo database."""

    def __init__(self, pool: AsyncConnectionPool):
        self.pool = pool

    async def get_student_profile_by_user(self, user_id: uuid.UUID) -> dict[str, Any] | None:
        """Resolve the academic student profile for an authenticated user.

        Identity binding: current_user.id -> student_profiles.user_id -> academic data. Returns
        None when the user has no student profile so the route can raise a clear 404.
        """
        row = await self._fetchone(
            """
            select
                sp.id,
                sp.user_id,
                coalesce(sp.student_code, sp.student_id) as student_code,
                coalesce(sp.full_name, u.full_name) as full_name,
                coalesce(sp.current_year, sp.academic_year) as current_year,
                coalesce(sp.cohort_year, sp.cohort) as cohort_year,
                coalesce(sp.status, sp.student_status) as status,
                f.id as faculty_id,
                f.code as faculty_code,
                f.name as faculty_name,
                p.id as program_id,
                p.code as program_code,
                p.name as program_name,
                p.degree_level as program_degree_level,
                p.curriculum_year as program_curriculum_year,
                p.total_required_credits as program_total_required_credits
            from student_profiles sp
            join users u on u.id = sp.user_id
            left join faculties f on f.id = sp.faculty_id
            left join programs p on p.id = sp.program_id
            where sp.user_id = %s
            """,
            (user_id,),
        )
        return dict(row) if row is not None else None

    async def get_current_term(self, *, on_date: date | None = None) -> dict[str, Any] | None:
        """The academic term whose date range contains ``on_date`` (today by default).

        Falls back to the most recent term that has already started so the overview/eligibility
        endpoints still resolve a sensible "current" term outside any teaching window.
        """
        date_expr = "current_date" if on_date is None else "%s"
        params: tuple[Any, ...] = () if on_date is None else (on_date, on_date)
        row = await self._fetchone(
            f"""
            select id, code, name, start_date, end_date, academic_year, term_order
            from academic_terms
            order by
                ({date_expr} between start_date and end_date) desc,
                (start_date <= {date_expr}) desc,
                start_date desc
            limit 1
            """,
            params,
        )
        return dict(row) if row is not None else None

    async def get_faculties(self) -> list[dict[str, Any]]:
        rows = await self._fetchall(
            """
            select id, code, name
            from faculties
            order by code
            """,
            (),
        )
        return [dict(row) for row in rows]

    async def get_programs(self) -> list[dict[str, Any]]:
        rows = await self._fetchall(
            """
            select
                p.id,
                p.faculty_id,
                f.code as faculty_code,
                f.name as faculty_name,
                p.code,
                p.name,
                p.degree_level,
                p.curriculum_year,
                p.total_required_credits
            from programs p
            join faculties f on f.id = p.faculty_id
            order by f.code, p.code, p.curriculum_year
            """,
            (),
        )
        return [dict(row) for row in rows]

    async def get_courses(self) -> list[dict[str, Any]]:
        rows = await self._fetchall(
            """
            select
                id,
                coalesce(code, course_code) as code,
                coalesce(name, course_title) as name,
                coalesce(name_vi, course_title_vi) as name_vi,
                credits,
                instructor as instructor_name,
                course_level,
                department_code,
                is_general_education,
                description
            from courses
            where is_active = true
            order by coalesce(code, course_code)
            """,
            (),
        )
        return [dict(row) for row in rows]

    async def get_curriculum(self, program_id: uuid.UUID) -> list[dict[str, Any]]:
        rows = await self._fetchall(
            """
            select
                cc.id,
                cc.program_id,
                cc.category,
                cc.is_required,
                cc.suggested_year,
                cc.suggested_term,
                cc.min_required_grade_4,
                c.id as course_id,
                coalesce(c.code, c.course_code) as course_code,
                coalesce(c.name, c.course_title) as course_name,
                coalesce(c.name_vi, c.course_title_vi) as course_name_vi,
                c.credits,
                c.instructor as instructor_name,
                c.course_level,
                c.department_code,
                c.is_general_education,
                c.description
            from curriculum_courses cc
            join courses c on c.id = cc.course_id
            where cc.program_id = %s
            order by cc.suggested_year nulls last, cc.suggested_term nulls last, course_code
            """,
            (program_id,),
        )
        return [dict(row) for row in rows]

    async def get_course_requisites(self, course_id: uuid.UUID) -> list[dict[str, Any]]:
        rows = await self._fetchall(
            """
            select
                cr.id,
                cr.course_id,
                cr.requisite_type,
                cr.min_grade_4,
                cr.note,
                required.id as required_course_id,
                coalesce(required.code, required.course_code) as required_course_code,
                coalesce(required.name, required.course_title) as required_course_name,
                coalesce(required.name_vi, required.course_title_vi) as required_course_name_vi,
                required.credits as required_course_credits
            from course_requisites cr
            join courses required on required.id = cr.required_course_id
            where cr.course_id = %s
            order by cr.requisite_type, required_course_code
            """,
            (course_id,),
        )
        return [dict(row) for row in rows]

    async def get_student_transcript(self, student_id: uuid.UUID) -> list[dict[str, Any]]:
        rows = await self._fetchall(
            """
            select
                sce.id,
                sce.student_id,
                sce.status,
                sce.attempt_no,
                sce.is_improvement,
                sce.retake_of_enrollment_id,
                sce.grade_10,
                sce.grade_4,
                sce.letter_grade,
                sce.passed,
                sce.earned_credits,
                sce.is_gpa_counted,
                sce.completed_at,
                t.id as term_id,
                t.code as term_code,
                t.name as term_name,
                t.start_date,
                t.end_date,
                t.academic_year,
                t.term_order,
                c.id as course_id,
                coalesce(c.code, c.course_code) as course_code,
                coalesce(c.name, c.course_title) as course_name,
                coalesce(c.name_vi, c.course_title_vi) as course_name_vi,
                c.credits,
                coalesce(cs.instructor_name, c.instructor) as instructor_name,
                c.course_level,
                c.department_code,
                c.is_general_education,
                cs.id as section_id,
                cs.section_code
            from student_course_enrollments sce
            join academic_terms t on t.id = sce.term_id
            join courses c on c.id = sce.course_id
            left join course_sections cs on cs.id = sce.section_id
            where sce.student_id = %s
            order by t.start_date, course_code, sce.attempt_no
            """,
            (student_id,),
        )
        return [dict(row) for row in rows]

    async def get_student_timetable(
        self,
        *,
        student_id: uuid.UUID,
        term_code: str = "2026-SUMMER",
    ) -> list[dict[str, Any]]:
        rows = await self._fetchall(
            """
            select
                se.id,
                se.section_id,
                se.title,
                se.meeting_type,
                se.start_at,
                se.end_at,
                se.note,
                cs.section_code,
                coalesce(se.instructor, cs.instructor_name) as instructor_name,
                coalesce(c.code, c.course_code) as course_code,
                coalesce(c.name, c.course_title) as course_name,
                coalesce(c.name_vi, c.course_title_vi) as course_name_vi,
                null::uuid as room_id,
                se.building,
                se.room as room_name,
                null::integer as room_capacity
            from student_schedule_events se
            join student_course_enrollments sce on sce.id = se.enrollment_id
            join academic_terms t on t.id = sce.term_id
            left join course_sections cs on cs.id = se.section_id
            left join courses c on c.id = se.course_id
            where se.student_id = %s
              and t.code = %s
              and sce.status in ('planned', 'enrolled', 'retaking', 'improvement')
            order by se.start_at, course_code, se.title
            """,
            (student_id, term_code),
        )
        return [dict(row) for row in rows]

    async def get_student_meetings_in_range(
        self,
        *,
        student_id: uuid.UUID,
        start_at: datetime,
        end_at: datetime,
    ) -> list[dict[str, Any]]:
        """Calendar events for the student within a datetime window.

        Used by the month-scoped schedule endpoint. Spans terms (the window, not a term code,
        bounds the result) so a month that straddles two terms still returns every meeting.
        """
        rows = await self._fetchall(
            """
            select
                se.id,
                se.section_id,
                se.title,
                se.meeting_type,
                se.start_at,
                se.end_at,
                se.note,
                cs.section_code,
                coalesce(se.instructor, cs.instructor_name) as instructor_name,
                coalesce(c.code, c.course_code) as course_code,
                coalesce(c.name, c.course_title) as course_name,
                coalesce(c.name_vi, c.course_title_vi) as course_name_vi,
                null::uuid as room_id,
                se.building,
                se.room as room_name,
                null::integer as room_capacity
            from student_schedule_events se
            left join student_course_enrollments sce on sce.id = se.enrollment_id
            left join course_sections cs on cs.id = se.section_id
            left join courses c on c.id = se.course_id
            where se.student_id = %s
              and (se.enrollment_id is null or sce.status in ('planned', 'enrolled', 'retaking', 'improvement'))
              and se.start_at >= %s
              and se.start_at < %s
            order by se.start_at, course_code, se.title
            """,
            (student_id, start_at, end_at),
        )
        return [dict(row) for row in rows]

    async def get_requisite_status_bulk(
        self,
        *,
        student_id: uuid.UUID,
        course_ids: list[uuid.UUID],
        term_id: uuid.UUID,
    ) -> dict[uuid.UUID, list[dict[str, Any]]]:
        """Requisite satisfaction for many courses at once, grouped by ``course_id``.

        Same per-requisite logic as ``get_requisite_status`` but evaluated for a set of courses in
        one query so eligibility can be computed across a whole curriculum without N round-trips.
        """
        if not course_ids:
            return {}
        rows = await self._fetchall(
            """
            select
                cr.id,
                cr.course_id,
                cr.required_course_id,
                cr.requisite_type,
                cr.min_grade_4,
                cr.note,
                coalesce(required.code, required.course_code) as required_course_code,
                coalesce(required.name, required.course_title) as required_course_name,
                coalesce(required.name_vi, required.course_title_vi) as required_course_name_vi,
                exists (
                    select 1
                    from student_course_enrollments passed_sce
                    join academic_terms passed_term on passed_term.id = passed_sce.term_id
                    join academic_terms target_term on target_term.id = %s
                    where passed_sce.student_id = %s
                      and passed_sce.course_id = cr.required_course_id
                      and passed_sce.passed = true
                      and passed_sce.grade_4 >= coalesce(cr.min_grade_4, 1.00)
                      and passed_term.end_date < target_term.start_date
                ) as required_passed_before_term,
                exists (
                    select 1
                    from student_course_enrollments same_term_sce
                    where same_term_sce.student_id = %s
                      and same_term_sce.course_id = cr.required_course_id
                      and same_term_sce.term_id = %s
                      and same_term_sce.status = any(%s)
                ) as required_enrolled_same_term
            from course_requisites cr
            join courses required on required.id = cr.required_course_id
            where cr.course_id = any(%s)
            order by cr.course_id, cr.requisite_type, required_course_code
            """,
            (
                term_id,
                student_id,
                student_id,
                term_id,
                list(SAME_TERM_REQUISITE_STATUSES),
                course_ids,
            ),
        )
        grouped: dict[uuid.UUID, list[dict[str, Any]]] = {}
        for row in rows:
            record = dict(row)
            record["satisfied"] = requisite_is_satisfied(
                requisite_type=record["requisite_type"],
                required_passed=record["required_passed_before_term"],
                required_same_term=record["required_enrolled_same_term"],
            )
            grouped.setdefault(record["course_id"], []).append(record)
        return grouped

    async def get_requisite_status(
        self,
        *,
        student_id: uuid.UUID,
        course_id: uuid.UUID,
        term_id: uuid.UUID,
    ) -> list[dict[str, Any]]:
        rows = await self._fetchall(
            """
            select
                cr.id,
                cr.course_id,
                cr.required_course_id,
                cr.requisite_type,
                cr.min_grade_4,
                cr.note,
                coalesce(required.code, required.course_code) as required_course_code,
                coalesce(required.name, required.course_title) as required_course_name,
                coalesce(required.name_vi, required.course_title_vi) as required_course_name_vi,
                exists (
                    select 1
                    from student_course_enrollments passed_sce
                    join academic_terms passed_term on passed_term.id = passed_sce.term_id
                    join academic_terms target_term on target_term.id = %s
                    where passed_sce.student_id = %s
                      and passed_sce.course_id = cr.required_course_id
                      and passed_sce.passed = true
                      and passed_sce.grade_4 >= coalesce(cr.min_grade_4, 1.00)
                      and passed_term.end_date < target_term.start_date
                ) as required_passed_before_term,
                exists (
                    select 1
                    from student_course_enrollments same_term_sce
                    where same_term_sce.student_id = %s
                      and same_term_sce.course_id = cr.required_course_id
                      and same_term_sce.term_id = %s
                      and same_term_sce.status = any(%s)
                ) as required_enrolled_same_term
            from course_requisites cr
            join courses required on required.id = cr.required_course_id
            where cr.course_id = %s
            order by cr.requisite_type, required_course_code
            """,
            (
                term_id,
                student_id,
                student_id,
                term_id,
                list(SAME_TERM_REQUISITE_STATUSES),
                course_id,
            ),
        )
        statuses: list[dict[str, Any]] = []
        for row in rows:
            record = dict(row)
            record["satisfied"] = requisite_is_satisfied(
                requisite_type=record["requisite_type"],
                required_passed=record["required_passed_before_term"],
                required_same_term=record["required_enrolled_same_term"],
            )
            statuses.append(record)
        return statuses

    async def _fetchone(self, query: str, params: tuple[Any, ...]) -> dict[str, Any] | None:
        async with self.pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, params)
                return await cur.fetchone()

    async def _fetchall(self, query: str, params: tuple[Any, ...]) -> list[dict[str, Any]]:
        async with self.pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, params)
                rows = await cur.fetchall()
        return list(rows)
