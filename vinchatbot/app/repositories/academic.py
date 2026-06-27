from __future__ import annotations

import uuid
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
                credits,
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
                c.credits,
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
                c.credits,
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
                cm.id,
                cm.section_id,
                cm.title,
                cm.meeting_type,
                cm.start_at,
                cm.end_at,
                cm.note,
                coalesce(c.code, c.course_code) as course_code,
                coalesce(c.name, c.course_title) as course_name,
                r.id as room_id,
                r.building,
                r.room_name,
                r.capacity as room_capacity
            from student_course_enrollments sce
            join academic_terms t on t.id = sce.term_id
            join course_sections cs on cs.id = sce.section_id
            join courses c on c.id = cs.course_id
            join class_meetings cm on cm.section_id = cs.id
            left join rooms r on r.id = cm.room_id
            where sce.student_id = %s
              and t.code = %s
              and sce.status in ('planned', 'enrolled', 'completed', 'retaking', 'improvement')
            order by cm.start_at, course_code, cm.title
            """,
            (student_id, term_code),
        )
        return [dict(row) for row in rows]

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

    async def _fetchall(self, query: str, params: tuple[Any, ...]) -> list[dict[str, Any]]:
        async with self.pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, params)
                rows = await cur.fetchall()
        return list(rows)
