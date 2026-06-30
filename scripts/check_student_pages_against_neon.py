from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from decimal import Decimal
from typing import Any

from psycopg.rows import dict_row

from vinchatbot.app.core.config import get_settings
from vinchatbot.app.core.timeutils import VINUNI_TZ, now_in_vietnam
from vinchatbot.app.db.connection import close_app_db_pool, open_readonly_app_db_pool
from vinchatbot.app.repositories.academic import AcademicRepository
from vinchatbot.app.services import academic as academic_service

DEFAULT_EMAILS = (
    "student.cs.demo@vinuni.edu.vn",
    "student.business.demo@vinuni.edu.vn",
    "student.health.demo@vinuni.edu.vn",
    "student.liberal.demo@vinuni.edu.vn",
)

ACTIVE_STATUSES = ("planned", "enrolled", "retaking", "improvement")
SCHEDULE_STATUSES = ("planned", "enrolled", "completed", "retaking", "improvement")
GPA_STATUSES = ("completed", "failed", "improvement")


@dataclass(frozen=True)
class Check:
    name: str
    page_value: Any
    db_value: Any

    @property
    def ok(self) -> bool:
        return _norm(self.page_value) == _norm(self.db_value)

    def as_dict(self) -> dict[str, Any]:
        return {
            "check": self.name,
            "ok": self.ok,
            "page_value": _jsonable(self.page_value),
            "db_value": _jsonable(self.db_value),
        }


def _jsonable(value: Any) -> Any:
    if isinstance(value, Decimal):
        return f"{value:.2f}"
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, tuple):
        return [_jsonable(v) for v in value]
    if isinstance(value, list):
        return [_jsonable(v) for v in value]
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    return value


def _norm(value: Any) -> Any:
    if isinstance(value, Decimal):
        return f"{value:.2f}"
    if isinstance(value, tuple):
        return tuple(_norm(v) for v in value)
    if isinstance(value, list):
        return [_norm(v) for v in value]
    return value


async def fetchone(pool: Any, query: str, params: tuple[Any, ...]) -> dict[str, Any] | None:
    async with pool.connection() as conn:
        conn.row_factory = dict_row
        async with conn.cursor() as cur:
            await cur.execute(query, params)
            return await cur.fetchone()


async def fetchall(pool: Any, query: str, params: tuple[Any, ...]) -> list[dict[str, Any]]:
    async with pool.connection() as conn:
        conn.row_factory = dict_row
        async with conn.cursor() as cur:
            await cur.execute(query, params)
            rows = await cur.fetchall()
    return [dict(row) for row in rows]


async def raw_academic_summary(
    pool: Any,
    *,
    student_id: Any,
    current_term_id: Any | None,
    program_id: Any | None,
    month_start: datetime,
    month_end: datetime,
    today_start: datetime,
    today_end: datetime,
) -> dict[str, Any]:
    cpa_row = await fetchone(
        pool,
        """
        select round((sum(sce.grade_4 * c.credits) / nullif(sum(c.credits), 0))::numeric, 2) as cpa,
               coalesce(sum(c.credits), 0)::int as gpa_credits
        from student_course_enrollments sce
        join courses c on c.id = sce.course_id
        where sce.student_id = %s
          and c.credits > 0
          and sce.status = any(%s)
          and sce.is_gpa_counted = true
          and sce.grade_4 is not null
        """,
        (student_id, list(GPA_STATUSES)),
    )
    term_rows = await fetchall(
        pool,
        """
        select t.id,
               t.code,
               round((sum(sce.grade_4 * c.credits) / nullif(sum(c.credits), 0))::numeric, 2) as term_gpa
        from academic_terms t
        left join student_course_enrollments sce
          on sce.term_id = t.id
         and sce.student_id = %s
         and sce.status = any(%s)
         and sce.is_gpa_counted = true
         and sce.grade_4 is not null
        left join courses c on c.id = sce.course_id and c.credits > 0
        group by t.id, t.code, t.start_date
        order by t.start_date
        """,
        (student_id, list(GPA_STATUSES)),
    )
    current_gpa = None
    for row in term_rows:
        if current_term_id is not None and row["id"] == current_term_id:
            current_gpa = row["term_gpa"]
            break
    if current_gpa is None:
        for row in term_rows:
            if row["term_gpa"] is not None:
                current_gpa = row["term_gpa"]

    earned_row = await fetchone(
        pool,
        """
        select coalesce(sum(credits), 0)::int as earned_credits
        from (
            select distinct on (sce.course_id) sce.course_id, c.credits
            from student_course_enrollments sce
            join courses c on c.id = sce.course_id
            where sce.student_id = %s
              and sce.passed = true
            order by sce.course_id
        ) passed_courses
        """,
        (student_id,),
    )
    attempted_row = await fetchone(
        pool,
        """
        select coalesce(sum(c.credits), 0)::int as attempted_credits
        from student_course_enrollments sce
        join courses c on c.id = sce.course_id
        where sce.student_id = %s
          and sce.status = any(%s)
        """,
        (student_id, ["completed", "failed", "improvement", "retaking"]),
    )
    required_row = await fetchone(
        pool,
        "select total_required_credits from programs where id = %s",
        (program_id,),
    ) if program_id is not None else None
    active_rows = await fetchall(
        pool,
        """
        select distinct coalesce(c.code, c.course_code) as code
        from student_course_enrollments sce
        join courses c on c.id = sce.course_id
        where sce.student_id = %s
          and sce.term_id = %s
          and sce.status = any(%s)
        order by code
        """,
        (student_id, current_term_id, list(ACTIVE_STATUSES)),
    ) if current_term_id is not None else []
    counts_row = await fetchone(
        pool,
        """
        select
            count(*)::int as transcript_enrollments,
            count(distinct term_id)::int as transcript_terms
        from student_course_enrollments
        where student_id = %s
        """,
        (student_id,),
    )
    curriculum_row = await fetchone(
        pool,
        """
        select
            count(*)::int as curriculum_courses,
            count(*) filter (where is_required)::int as required_courses
        from curriculum_courses
        where program_id = %s
        """,
        (program_id,),
    ) if program_id is not None else {"curriculum_courses": 0, "required_courses": 0}
    meeting_row = await fetchone(
        pool,
        """
        select
            count(*)::int as month_meetings,
            count(*) filter (where cm.start_at >= %s and cm.start_at < %s)::int as today_meetings
        from student_course_enrollments sce
        join course_sections cs on cs.id = sce.section_id
        join class_meetings cm on cm.section_id = cs.id
        where sce.student_id = %s
          and sce.status = any(%s)
          and cm.start_at >= %s
          and cm.start_at < %s
        """,
        (
            today_start,
            today_end,
            student_id,
            list(SCHEDULE_STATUSES),
            month_start,
            month_end,
        ),
    )
    return {
        "current_gpa": current_gpa,
        "cpa": cpa_row["cpa"] if cpa_row else None,
        "gpa_credits": cpa_row["gpa_credits"] if cpa_row else 0,
        "earned_credits": earned_row["earned_credits"] if earned_row else 0,
        "attempted_credits": attempted_row["attempted_credits"] if attempted_row else 0,
        "required_credits": required_row["total_required_credits"] if required_row else 0,
        "active_current_course_codes": [row["code"] for row in active_rows],
        "transcript_enrollments": counts_row["transcript_enrollments"] if counts_row else 0,
        "transcript_terms": counts_row["transcript_terms"] if counts_row else 0,
        "curriculum_courses": curriculum_row["curriculum_courses"] if curriculum_row else 0,
        "required_courses": curriculum_row["required_courses"] if curriculum_row else 0,
        "month_meetings": meeting_row["month_meetings"] if meeting_row else 0,
        "today_meetings": meeting_row["today_meetings"] if meeting_row else 0,
    }


async def check_email(pool: Any, email: str, now: datetime) -> dict[str, Any]:
    repository = AcademicRepository(pool)
    user = await fetchone(pool, "select id, email from users where email = %s", (email,))
    if user is None:
        return {"email": email, "status": "missing_user", "checks": []}

    profile = await repository.get_student_profile_by_user(user["id"])
    if profile is None:
        return {"email": email, "status": "missing_student_profile", "checks": []}

    current_term = await repository.get_current_term(on_date=now.date())
    enrollments = await repository.get_student_transcript(profile["id"])
    curriculum = await repository.get_curriculum(profile["program_id"]) if profile.get("program_id") else []
    month_start, month_end = academic_service.month_window(now.year, now.month)
    today_start = datetime.combine(now.date(), time.min, tzinfo=VINUNI_TZ)
    today_end = today_start + timedelta(days=1)
    monthly_meetings = await repository.get_student_meetings_in_range(
        student_id=profile["id"],
        start_at=month_start,
        end_at=month_end,
    )
    today_meetings = [
        meeting for meeting in monthly_meetings if today_start <= meeting["start_at"] < today_end
    ]

    upcoming = await repository.get_student_meetings_in_range(
        student_id=profile["id"],
        start_at=now,
        end_at=now + timedelta(days=30),
    )
    overview = academic_service.build_overview(
        profile=profile,
        current_term=current_term,
        enrollments=enrollments,
        curriculum=curriculum,
        upcoming_meetings=upcoming[:8],
    )
    transcript = academic_service.build_transcript(profile["id"], enrollments)
    curriculum_progress = academic_service.build_curriculum_progress(
        program=profile if profile.get("program_id") else None,
        curriculum=curriculum,
        enrollments=enrollments,
    )
    requisites_by_course = {}
    if current_term is not None and curriculum:
        requisites_by_course = await repository.get_requisite_status_bulk(
            student_id=profile["id"],
            course_ids=[row["course_id"] for row in curriculum],
            term_id=current_term["id"],
        )
    eligibility = academic_service.build_course_eligibility(
        term=current_term,
        curriculum=curriculum,
        enrollments=enrollments,
        requisites_by_course=requisites_by_course,
    )
    raw = await raw_academic_summary(
        pool,
        student_id=profile["id"],
        current_term_id=current_term["id"] if current_term else None,
        program_id=profile.get("program_id"),
        month_start=month_start,
        month_end=month_end,
        today_start=today_start,
        today_end=today_end,
    )

    overview_active_codes = sorted(course.code for course in overview.enrolled_courses)
    transcript_enrollment_count = sum(len(term.enrollments) for term in transcript.terms)
    checks = [
        Check("dashboard.current_gpa", overview.current_gpa, raw["current_gpa"]),
        Check("dashboard.cumulative_cpa", overview.cumulative_cpa, raw["cpa"]),
        Check("dashboard.earned_credits", overview.earned_credits, raw["earned_credits"]),
        Check("dashboard.required_credits", overview.required_credits, raw["required_credits"]),
        Check("dashboard.currently_studying_codes", overview_active_codes, raw["active_current_course_codes"]),
        Check("dashboard.month_schedule_count", len(monthly_meetings), raw["month_meetings"]),
        Check("dashboard.today_schedule_count", len(today_meetings), raw["today_meetings"]),
        Check("academic.transcript_terms", len(transcript.terms), raw["transcript_terms"]),
        Check("academic.transcript_enrollments", transcript_enrollment_count, raw["transcript_enrollments"]),
        Check("academic.transcript_summary_gpa", transcript.summary.gpa, raw["cpa"]),
        Check("academic.transcript_summary_gpa_credits", transcript.summary.gpa_credits, raw["gpa_credits"]),
        Check("academic.transcript_summary_attempted_credits", transcript.summary.attempted_credits, raw["attempted_credits"]),
        Check("academic.curriculum_required_credits", curriculum_progress.summary.required_credits, raw["required_credits"]),
    ]
    return {
        "email": email,
        "status": "ok" if all(check.ok for check in checks) else "mismatch",
        "student_code": profile.get("student_code"),
        "program": profile.get("program_code"),
        "current_term": current_term["code"] if current_term else None,
        "dashboard_visible_summary": {
            "gpa": overview.current_gpa,
            "cpa": overview.cumulative_cpa,
            "credits": f"{overview.earned_credits}/{overview.required_credits}",
            "progress_percent": overview.summary.progress_percent,
            "required_done_left": (
                overview.summary.completed_required_courses,
                overview.summary.remaining_required_courses,
            ),
            "currently_studying": overview_active_codes,
            "month_schedule_count": len(monthly_meetings),
            "today_schedule_count": len(today_meetings),
        },
        "academic_visible_summary": {
            "terms": len(transcript.terms),
            "enrollments": transcript_enrollment_count,
            "curriculum": {
                "completed": len(curriculum_progress.completed),
                "in_progress": len(curriculum_progress.in_progress),
                "failed": len(curriculum_progress.failed),
                "remaining_required": len(curriculum_progress.remaining_required),
                "remaining_zero_credit": len(curriculum_progress.remaining_zero_credit),
            },
            "eligibility": {
                "eligible": len(eligibility.eligible),
                "blocked": len(eligibility.blocked),
            },
        },
        "checks": [check.as_dict() for check in checks],
    }


async def main_async(emails: list[str]) -> int:
    settings = get_settings()
    pool = await open_readonly_app_db_pool(settings)
    if pool is None:
        print("App database is not configured.")
        return 2
    try:
        now = now_in_vietnam()
        results = [await check_email(pool, email, now) for email in emails]
        payload = {
            "checked_at_vietnam": now.isoformat(),
            "month": f"{now.year}-{now.month:02d}",
            "results": results,
        }
        print(json.dumps(_jsonable(payload), ensure_ascii=False, indent=2))
        return 0 if all(result["status"] == "ok" for result in results) else 1
    finally:
        await close_app_db_pool()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compare student dashboard/academic page read-models with live Neon rows."
    )
    parser.add_argument(
        "--email",
        action="append",
        dest="emails",
        help="Student email to check. Can be repeated. Defaults to primary demo students.",
    )
    args = parser.parse_args()
    return asyncio.run(main_async(args.emails or list(DEFAULT_EMAILS)))


if __name__ == "__main__":
    raise SystemExit(main())
