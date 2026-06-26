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
            select
                sp.id,
                sp.student_id,
                sp.program,
                sp.major,
                sp.cohort,
                sp.academic_year,
                sp.student_status,
                sp.preferred_language,
                sp.advisor_name,
                sp.advisor_email,
                sp.ai_personalization_enabled,
                i.id as institute_id,
                i.code as institute_code,
                i.name_vi as institute_name_vi,
                i.name_en as institute_name_en,
                a.gpa,
                a.credits_earned,
                a.credits_required,
                a.current_semester,
                a.academic_status,
                a.updated_at as academic_summary_updated_at
            from student_profiles sp
            join institutes i on i.id = sp.institute_id
            left join academic_summaries a on a.student_profile_id = sp.id
            where sp.user_id = %s
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
                c.course_code,
                c.course_title,
                c.credits,
                c.semester,
                c.academic_year,
                c.instructor,
                i.id as institute_id,
                i.code as institute_code,
                i.name_vi as institute_name_vi,
                i.name_en as institute_name_en
            from enrollments e
            join courses c on c.id = e.course_id
            left join institutes i on i.id = c.institute_id
            where e.student_profile_id = %s
            order by c.course_code
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
                s.id,
                s.course_id,
                c.course_code,
                c.course_title,
                s.title,
                s.schedule_type,
                s.start_time,
                s.end_time,
                s.location,
                s.building,
                s.room,
                s.instructor,
                s.recurrence_rule
            from schedules s
            left join courses c on c.id = s.course_id
            where s.student_profile_id = %s
              and (%s = false or s.end_time >= now())
            order by s.start_time, s.title
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
                c.course_code,
                c.course_title,
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
                c.course_code,
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
                c.course_code,
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
            from enrollments
            where student_profile_id = %s
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
