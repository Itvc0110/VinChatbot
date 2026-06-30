from __future__ import annotations

import uuid
from typing import Any

from psycopg_pool import AsyncConnectionPool


class StudentRepository:
    """Read-only repository for current-student portal data."""

    def __init__(self, pool: AsyncConnectionPool):
        self.pool = pool

    async def get_current_student_profile(self, user_id: uuid.UUID) -> dict[str, Any] | None:
        row = await self._fetchone(
            """
            with profile as (
                select
                    sp.id,
                    coalesce(sp.student_code, sp.student_id) as student_id,
                    coalesce(sp.program, p.name) as program,
                    coalesce(sp.major, p.name) as major,
                    coalesce(sp.cohort, sp.cohort_year) as cohort,
                    coalesce(sp.academic_year, sp.current_year) as academic_year,
                    coalesce(sp.student_status, sp.status, 'active') as student_status,
                    sp.preferred_language,
                    sp.advisor_name,
                    sp.advisor_email,
                    sp.ai_personalization_enabled,
                    sp.institute_id,
                    sp.updated_at,
                    coalesce(p.total_required_credits, 120) as credits_required
                from student_profiles sp
                left join programs p on p.id = sp.program_id
                where sp.user_id = %s
            ),
            current_term as (
                select t.name
                from academic_terms t
                order by
                    (current_date between t.start_date and t.end_date) desc,
                    (t.start_date <= current_date) desc,
                    t.start_date desc
                limit 1
            ),
            summary as (
                select
                    p.id as student_profile_id,
                    round(
                        (
                            sum(sce.grade_4 * c.credits) filter (
                                where c.credits > 0
                                  and sce.status in ('completed', 'failed', 'improvement')
                                  and sce.is_gpa_counted = true
                                  and sce.grade_4 is not null
                            )
                            / nullif(
                                sum(c.credits) filter (
                                    where c.credits > 0
                                      and sce.status in ('completed', 'failed', 'improvement')
                                      and sce.is_gpa_counted = true
                                      and sce.grade_4 is not null
                                ),
                                0
                            )
                        )::numeric,
                        2
                    ) as gpa,
                    coalesce(sum(sce.earned_credits) filter (where sce.passed = true), 0)::int
                        as credits_earned,
                    p.credits_required,
                    max(sce.updated_at) as enrollment_updated_at
                from profile p
                left join student_course_enrollments sce on sce.student_id = p.id
                left join courses c on c.id = sce.course_id
                group by p.id, p.credits_required
            )
            select
                p.id,
                p.student_id,
                p.program,
                p.major,
                p.cohort,
                p.academic_year,
                p.student_status,
                p.preferred_language,
                p.advisor_name,
                p.advisor_email,
                p.ai_personalization_enabled,
                i.id as institute_id,
                i.code as institute_code,
                i.name_vi as institute_name_vi,
                i.name_en as institute_name_en,
                s.gpa,
                s.credits_earned,
                s.credits_required,
                (select name from current_term) as current_semester,
                case
                    when s.gpa is null then 'normal'
                    when s.gpa < 1.50 then 'probation'
                    when s.gpa < 2.00 then 'warning'
                    else 'normal'
                end as academic_status,
                greatest(p.updated_at, coalesce(s.enrollment_updated_at, p.updated_at))
                    as academic_summary_updated_at
            from profile p
            join institutes i on i.id = p.institute_id
            join summary s on s.student_profile_id = p.id
            """,
            (user_id,),
        )
        if row is None:
            return None
        return self._student_profile_from_row(row)

    async def get_courses(self, student_profile_id: uuid.UUID) -> list[dict[str, Any]]:
        rows = await self._fetchall(
            """
            select
                c.id,
                coalesce(c.code, c.course_code) as course_code,
                coalesce(c.name, c.course_title) as course_title,
                coalesce(c.name_vi, c.course_title_vi) as course_title_vi,
                c.credits,
                c.semester,
                c.academic_year,
                coalesce(cs.instructor_name, c.instructor) as instructor,
                i.id as institute_id,
                i.code as institute_code,
                i.name_vi as institute_name_vi,
                i.name_en as institute_name_en
            from student_course_enrollments sce
            join student_profiles sp on sp.id = sce.student_id
            join courses c on c.id = sce.course_id
            left join course_sections cs on cs.id = sce.section_id
            left join institutes i on i.id = coalesce(c.institute_id, sp.institute_id)
            where sce.student_id = %s
              and sce.status in ('planned', 'enrolled', 'retaking', 'improvement')
            order by coalesce(c.code, c.course_code)
            """,
            (student_profile_id,),
        )
        return [self._course_from_row(row) for row in rows]

    async def get_schedule(
        self,
        student_profile_id: uuid.UUID,
        *,
        upcoming_only: bool = True,
    ) -> list[dict[str, Any]]:
        rows = await self._fetchall(
            """
            select
                se.id,
                se.course_id,
                coalesce(c.code, c.course_code) as course_code,
                coalesce(c.name, c.course_title) as course_title,
                coalesce(c.name_vi, c.course_title_vi) as course_title_vi,
                se.title,
                case
                    when se.meeting_type in ('lecture', 'tutorial', 'seminar') then 'class'
                    when se.meeting_type = 'lab' then 'lab'
                    when se.meeting_type = 'exam' then 'exam'
                    when se.meeting_type = 'office_hour' then 'office_hour'
                    else 'other'
                end as schedule_type,
                se.start_at as start_time,
                se.end_at as end_time,
                se.location,
                se.building,
                se.room,
                se.instructor,
                null::text as recurrence_rule
            from student_schedule_events se
            left join courses c on c.id = se.course_id
            where se.student_id = %s
              and (%s = false or se.end_at >= now())
            order by se.start_at, se.title
            """,
            (student_profile_id, upcoming_only),
        )
        return [dict(row) for row in rows]

    async def get_deadlines(
        self,
        student_profile_id: uuid.UUID,
        *,
        upcoming_only: bool = True,
    ) -> list[dict[str, Any]]:
        rows = await self._fetchall(
            """
            select
                d.id,
                d.course_id,
                coalesce(c.code, c.course_code) as course_code,
                coalesce(c.name, c.course_title) as course_title,
                coalesce(c.name_vi, c.course_title_vi) as course_title_vi,
                d.title,
                d.kind,
                d.due_at,
                d.source_title,
                d.source_url
            from deadlines d
            left join courses c on c.id = d.course_id
            where d.student_profile_id = %s
              and (%s = false or d.due_at >= now())
            order by d.due_at, d.title
            """,
            (student_profile_id, upcoming_only),
        )
        return [dict(row) for row in rows]

    async def get_notifications(
        self,
        *,
        user_id: uuid.UUID,
        profile: dict[str, Any],
    ) -> list[dict[str, Any]]:
        course_ids = await self._fetch_enrolled_course_ids(profile["id"])
        rows = await self._fetchall(
            """
            select
                n.id,
                n.type,
                n.title,
                n.message,
                n.priority,
                n.status,
                n.target_scope,
                n.institute_id,
                i.code as institute_code,
                n.course_id,
                coalesce(c.code, c.course_code) as course_code,
                n.cohort,
                n.deadline,
                n.event_date,
                n.start_date,
                n.end_date,
                n.source_title,
                n.source_url,
                n.created_at,
                n.updated_at,
                (nr.id is not null) as is_read,
                coalesce(nr.important, false) as important,
                coalesce(nr.archived, false) as archived
            from notifications n
            left join institutes i on i.id = n.institute_id
            left join courses c on c.id = n.course_id
            left join notification_reads nr
                on nr.notification_id = n.id
               and nr.user_id = %s
            where n.status = 'published'
              and (n.start_date is null or n.start_date <= now())
              and (n.end_date is null or n.end_date >= now())
              and (
                    n.target_scope = 'all'
                 or (n.target_scope = 'institute' and n.institute_id = %s)
                 or (n.target_scope = 'course' and n.course_id = any(%s))
                 or (n.target_scope = 'cohort' and n.cohort = %s)
              )
            order by n.priority desc, n.created_at desc, n.title
            """,
            (
                user_id,
                profile["institute"]["id"],
                course_ids,
                profile["cohort"],
            ),
        )
        return [dict(row) for row in rows]

    async def get_suggestions(self, profile: dict[str, Any]) -> list[dict[str, Any]]:
        course_ids = await self._fetch_enrolled_course_ids(profile["id"])
        rows = await self._fetchall(
            """
            select
                sq.id,
                sq.question_text,
                sq.source_type,
                sq.source_id,
                sq.notification_id,
                sq.topic,
                sq.intent,
                sq.category,
                sq.trigger_phase,
                sq.institute_id,
                i.code as institute_code,
                sq.course_id,
                coalesce(c.code, c.course_code) as course_code,
                sq.cohort,
                sq.score,
                sq.priority,
                sq.created_by_ai,
                sq.approved_by_admin,
                sq.is_active,
                sq.valid_from,
                sq.valid_until
            from suggested_questions sq
            left join institutes i on i.id = sq.institute_id
            left join courses c on c.id = sq.course_id
            where sq.is_active = true
              and (sq.valid_from is null or sq.valid_from <= now())
              and (sq.valid_until is null or sq.valid_until >= now())
              and (sq.institute_id is null or sq.institute_id = %s)
              and (sq.course_id is null or sq.course_id = any(%s))
              and (sq.cohort is null or sq.cohort = %s)
            order by sq.priority desc, sq.score desc, sq.question_text
            """,
            (profile["institute"]["id"], course_ids, profile["cohort"]),
        )
        return [dict(row) for row in rows]

    async def _fetch_enrolled_course_ids(self, student_profile_id: uuid.UUID) -> list[uuid.UUID]:
        rows = await self._fetchall(
            """
            select course_id
            from student_course_enrollments
            where student_id = %s
              and status in ('planned', 'enrolled', 'retaking', 'improvement')
            """,
            (student_profile_id,),
        )
        return [row["course_id"] for row in rows]

    def _student_profile_from_row(self, row: dict[str, Any]) -> dict[str, Any]:
        academic_summary = None
        if row["academic_status"] is not None:
            academic_summary = {
                "gpa": row["gpa"],
                "credits_earned": row["credits_earned"],
                "credits_required": row["credits_required"],
                "current_semester": row["current_semester"],
                "academic_status": row["academic_status"],
                "updated_at": row["academic_summary_updated_at"],
            }

        return {
            "id": row["id"],
            "student_id": row["student_id"],
            "program": row["program"],
            "major": row["major"],
            "cohort": row["cohort"],
            "academic_year": row["academic_year"],
            "student_status": row["student_status"],
            "preferred_language": row["preferred_language"],
            "advisor_name": row["advisor_name"],
            "advisor_email": row["advisor_email"],
            "ai_personalization_enabled": row["ai_personalization_enabled"],
            "institute": {
                "id": row["institute_id"],
                "code": row["institute_code"],
                "name_vi": row["institute_name_vi"],
                "name_en": row["institute_name_en"],
            },
            "academic_summary": academic_summary,
        }

    def _course_from_row(self, row: dict[str, Any]) -> dict[str, Any]:
        institute = None
        if row["institute_id"] is not None:
            institute = {
                "id": row["institute_id"],
                "code": row["institute_code"],
                "name_vi": row["institute_name_vi"],
                "name_en": row["institute_name_en"],
            }
        return {
            "id": row["id"],
            "course_code": row["course_code"],
            "course_title": row["course_title"],
            "course_title_vi": row["course_title_vi"],
            "credits": row["credits"],
            "semester": row["semester"],
            "academic_year": row["academic_year"],
            "instructor": row["instructor"],
            "institute": institute,
        }

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
