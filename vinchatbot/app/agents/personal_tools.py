"""Read-only, per-student-scoped DB tools for the "personal" specialist (Phase 5).

Security model (the whole point of this module):

- **Isolation by construction.** Every tool resolves the student from
  ``observability.get_student_identity()`` — a contextvar the chat route sets from the VERIFIED
  session before the agent runs. NO tool takes a student/user id parameter, so the LLM has no way to
  name another student; every SQL query is hard-scoped to this session's
  ``student_profile_id`` / ``user_id``. With the contextvar unset (anonymous / admin / no session)
  every tool refuses.
- **Read-only.** The tools reuse the existing SELECT-only repository methods over a pool whose
  sessions are forced ``default_transaction_read_only=on`` (see ``db/connection.py``); a write would
  raise. No ingestion, no mutation.
- **Compact, own-data-only output.** Tools return small JSON strings of the student's own data —
  schedule/courses/grades/credits/GPA/curriculum/eligibility + a deterministic GPA projection.

This is intentionally separate from the general RAG specialists (calendar/policy/financial/services),
which never get a DB tool.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from psycopg_pool import AsyncConnectionPool

from vinchatbot.app.core.config import Settings, get_settings
from vinchatbot.app.core.observability import StudentIdentity, get_student_identity
from vinchatbot.app.core.timeutils import VINUNI_TZ, now_in_vietnam, week_bounds
from vinchatbot.app.repositories.academic import AcademicRepository
from vinchatbot.app.repositories.students import StudentRepository
from vinchatbot.app.services import academic as academic_service

logger = logging.getLogger(__name__)

# VinUni "Excellent" (Xuất sắc) honor cutoff on the 4.0 scale. Documented here + in the specialist
# prompt; other honor cutoffs (Very Good / Good) are to be confirmed before exposing them.
EXCELLENT_GPA_4 = 4.0  # max grade on the 4.0 scale — used for feasibility checks
HONOR_CUTOFFS_4 = {"excellent": 3.6}

_REFUSAL = {
    "error": "not_signed_in",
    "message": (
        "This data is only available to a signed-in student about their OWN academic record. "
        "Ask the student to log in to their VinUni student account."
    ),
}

_SCHEDULE_WINDOWS = (
    "now",
    "today",
    "tomorrow",
    "this_week",
    "last_week",
    "next_week",
    "next",
    "all",
)

# The names the personal tools are exposed under (must match the @tool function names below). Used by
# the agent service to recognize that an answer was grounded in the read-only, own-data-only tools and
# may therefore be trusted through the output guard without official citations.
PERSONAL_TOOL_NAMES = frozenset(
    {
        "get_my_profile",
        "get_my_academic_standing",
        "get_my_schedule",
        "get_my_courses",
        "get_my_transcript",
        "get_my_deadlines",
        "get_my_curriculum_progress",
        "get_my_course_eligibility",
        "project_gpa_for_target",
    }
)


def _json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, default=_default)


def _default(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _error(message: str) -> str:
    return _json({"error": "unavailable", "message": message})


def _to_vn(value: Any) -> datetime | None:
    """Normalize a DB timestamp to VinUni local time. class_meetings are stored in UTC; a naive value
    is assumed UTC. Returns None for non-datetimes so callers can skip gracefully."""
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(VINUNI_TZ)


def _fmt(dt: datetime | None) -> str | None:
    return dt.strftime("%Y-%m-%d %H:%M") if dt else None


def _academic_meeting(row: dict) -> dict:
    """Build a meeting dict from an academic schedule row. Carries internal `_start`/`_end`
    (VN-localized datetimes) for current/next computation; strip them with `_strip_internal` before
    returning to the model."""
    start_vn = _to_vn(row.get("start_at"))
    end_vn = _to_vn(row.get("end_at"))
    return {
        "course_code": row.get("course_code"),
        "course_name": row.get("course_name"),
        "course_name_vi": row.get("course_name_vi"),
        "title": row.get("title"),
        "type": row.get("meeting_type"),
        "start": _fmt(start_vn),
        "end": _fmt(end_vn),
        "_start": start_vn,
        "_end": end_vn,
        "section": row.get("section_code"),
        "instructor": row.get("instructor_name"),
        "room": row.get("room_name"),
        "building": row.get("building"),
    }


def _student_api_meeting(row: dict) -> dict:
    """Build a meeting dict from the stable student schedule API shape."""
    start_vn = _to_vn(row.get("start_time"))
    end_vn = _to_vn(row.get("end_time"))
    return {
        "course_code": row.get("course_code"),
        "course_name": row.get("course_title"),
        "course_name_vi": row.get("course_title_vi"),
        "title": row.get("title"),
        "type": row.get("schedule_type"),
        "start": _fmt(start_vn),
        "end": _fmt(end_vn),
        "_start": start_vn,
        "_end": end_vn,
        "room": row.get("room"),
        "building": row.get("building"),
        "instructor": row.get("instructor"),
    }


def _strip_internal(meeting: dict | None) -> dict | None:
    if not meeting:
        return meeting
    return {k: v for k, v in meeting.items() if k not in ("_start", "_end")}


def _parse_date_range(
    from_date: str | None, to_date: str | None, now: datetime
) -> tuple[datetime, datetime] | None:
    """Parse optional ISO ``YYYY-MM-DD`` ``from_date``/``to_date`` into a half-open
    ``[start, end)`` range in ``now``'s timezone, with ``to_date`` INCLUSIVE (so end = to_date + 1d).

    Tolerant of one-sided input (a lone date → that single day) and bad input (returns None so the
    caller falls back to the named window). Returns None when neither date is given.
    """
    if not from_date and not to_date:
        return None

    def _one(value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            d = datetime.strptime(value.strip(), "%Y-%m-%d").date()
        except (ValueError, AttributeError):
            return None
        return datetime(d.year, d.month, d.day, tzinfo=now.tzinfo)

    start = _one(from_date)
    end_inclusive = _one(to_date)
    if start is None and end_inclusive is None:
        return None
    start = start or end_inclusive
    end_inclusive = end_inclusive or start
    end = end_inclusive + timedelta(days=1)
    if end <= start:
        end = start + timedelta(days=1)
    return start, end


def build_personal_tools(pool: AsyncConnectionPool, settings: Settings | None = None) -> list[Any]:
    """Build the read-only, session-scoped personal tools over the given (read-only) pool.

    Same closure pattern as build_retrieval_tools. The pool is the READ-ONLY app DB pool; the repos
    are SELECT-only. Returns LangChain @tools whose schemas expose NO id parameter.
    """
    settings = settings or get_settings()
    try:
        from langchain.tools import tool
    except ImportError as exc:  # pragma: no cover - langchain is a hard dep in the app image.
        raise RuntimeError("Install langchain to build personal tools.") from exc

    students = StudentRepository(pool)
    academic = AcademicRepository(pool)

    def _identity() -> StudentIdentity | None:
        return get_student_identity()

    async def _academic_record(ident: StudentIdentity) -> dict[str, Any] | None:
        profile = await academic.get_student_profile_by_user(ident.user_id)
        if profile is None:
            return None
        current_term = await academic.get_current_term()
        transcript = await academic.get_student_transcript(ident.student_profile_id)
        curriculum = (
            await academic.get_curriculum(profile["program_id"])
            if profile.get("program_id")
            else []
        )
        overview = academic_service.build_overview(
            profile=profile,
            current_term=current_term,
            enrollments=transcript,
            curriculum=curriculum,
            upcoming_meetings=[],
        )
        progress = academic_service.build_curriculum_progress(
            program=profile if profile.get("program_id") else None,
            curriculum=curriculum,
            enrollments=transcript,
        )
        return {
            "profile": profile,
            "current_term": current_term,
            "transcript": transcript,
            "curriculum": curriculum,
            "overview": overview,
            "progress": progress,
        }

    def _course_payload(course: Any, *, status: str | None = None, term: str | None = None) -> dict[str, Any]:
        payload = {
            "course_code": course.code,
            "course_title": course.name,
            "course_title_vi": course.name_vi,
            "credits": course.credits,
            "instructor": course.instructor_name,
            "course_level": course.course_level,
            "department_code": course.department_code,
        }
        if status is not None:
            payload["status"] = status
        if term is not None:
            payload["term"] = term
        return payload

    # ---- profile & standing -------------------------------------------------------------------

    @tool
    async def get_my_profile() -> str:
        """Return the signed-in student's own academic profile: student ID / student code, program,
        major, faculty/institute, cohort/intake year, advisor, and total required credits for their
        program. No input. Use for "what is my student ID / program / major / advisor / cohort?"
        type questions."""
        ident = _identity()
        if ident is None:
            return _json(_REFUSAL)
        try:
            portal = await students.get_current_student_profile(ident.user_id)
            acad = await academic.get_student_profile_by_user(ident.user_id)
        except Exception:
            logger.exception("get_my_profile failed.")
            return _error("Could not read the student profile right now.")
        if portal is None and acad is None:
            return _json({"found": False, "message": "No student profile on record."})
        portal = portal or {}
        acad = acad or {}
        return _json(
            {
                "found": True,
                "student_code": acad.get("student_code") or portal.get("student_id"),
                "program": acad.get("program_name") or portal.get("program"),
                "program_code": acad.get("program_code"),
                "major": portal.get("major") or acad.get("program_name"),
                "degree_level": acad.get("program_degree_level"),
                "faculty": acad.get("faculty_name"),
                "institute": (portal.get("institute") or {}).get("name_en"),
                "cohort": acad.get("cohort_year") or portal.get("cohort"),
                "academic_year": acad.get("current_year") or portal.get("academic_year"),
                "academic_status": acad.get("status") or portal.get("student_status"),
                "advisor_name": portal.get("advisor_name"),
                "advisor_email": portal.get("advisor_email"),
                "total_required_credits": acad.get("program_total_required_credits"),
            }
        )

    @tool
    async def get_my_academic_standing() -> str:
        """Return the signed-in student's GPA/CPA, credits earned, credits required, progress,
        academic standing/status, and current term from the same academic read-model used by the
        student dashboard. No input. Use for "what is my GPA / CPA / how many credits do I have /
        am I in good standing?"."""
        ident = _identity()
        if ident is None:
            return _json(_REFUSAL)
        try:
            record = await _academic_record(ident)
        except Exception:
            logger.exception("get_my_academic_standing failed.")
            return _error("Could not read the academic standing right now.")
        if record is None:
            return _json({"found": False, "message": "No academic profile on record yet."})
        overview = record["overview"]
        summary = overview.summary
        current_term = record["current_term"]
        profile = record["profile"]
        return _json(
            {
                "found": True,
                "gpa": overview.current_gpa,
                "current_gpa": overview.current_gpa,
                "cumulative_cpa": overview.cumulative_cpa,
                "gpa_scale": "4.0",
                "credits_earned": overview.earned_credits,
                "credits_required": overview.required_credits,
                "progress_percent": summary.progress_percent,
                "completed_required_courses": summary.completed_required_courses,
                "remaining_required_courses": summary.remaining_required_courses,
                "academic_status": profile.get("status"),
                "current_semester": current_term.get("code") if current_term else None,
            }
        )

    # ---- schedule -----------------------------------------------------------------------------

    @tool
    async def get_my_schedule(
        window: str = "today",
        from_date: str | None = None,
        to_date: str | None = None,
    ) -> str:
        """Return the signed-in student's own class schedule, in VinUni local time (Asia/Ho_Chi_Minh).

        Pick ONE selector:
        - window:
            "today"/"tomorrow"  → the WHOLE calendar day (INCLUDING classes already finished today),
            "this_week"/"last_week"/"next_week" → that calendar week, Monday→Sunday,
            "now"   → the class happening right now (or null) + the next one,
            "next"  → just the next upcoming class,
            "all"   → the next 30 days.
        - from_date / to_date: explicit ISO dates "YYYY-MM-DD" for an arbitrary INCLUSIVE range
            (e.g. one specific day → from_date == to_date). When given, they OVERRIDE `window`.

        Use "last_week"/"this_week"/"next_week" for "lịch tuần trước / tuần này / tuần sau"; "today"
        for "lịch hôm nay" (the answer must list the whole day, not only未学 classes); from_date/to_date
        for "lịch ngày 24/6". The result lists EVERY meeting in the resolved range (past and future
        within it), sorted by time, and ALWAYS includes "next_class" (soonest upcoming) and
        "current_class" (now, or null). An empty "meetings" list does NOT mean no upcoming class — use
        "next_class". Fields "range_start"/"range_end" are the resolved local dates (inclusive)."""
        ident = _identity()
        if ident is None:
            return _json(_REFUSAL)
        now = now_in_vietnam()
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        # Resolve the [range_start, range_end) window (end EXCLUSIVE). Explicit dates win over `window`.
        explicit = _parse_date_range(from_date, to_date, now)
        range_start: datetime | None
        range_end: datetime | None
        if explicit is not None:
            range_start, range_end = explicit
            window = "range"
        else:
            window = (window or "today").strip().lower()
            if window not in _SCHEDULE_WINDOWS:
                window = "today"
            if window == "today":
                range_start, range_end = day_start, day_start + timedelta(days=1)
            elif window == "tomorrow":
                range_start, range_end = day_start + timedelta(days=1), day_start + timedelta(days=2)
            elif window == "this_week":
                range_start, range_end = week_bounds(now, 0)
            elif window == "last_week":
                range_start, range_end = week_bounds(now, -1)
            elif window == "next_week":
                range_start, range_end = week_bounds(now, 1)
            elif window == "all":
                range_start, range_end = day_start, now + timedelta(days=30)
            else:  # now / next — answered from the broad scan below, no range listing
                range_start, range_end = None, None

        # Authoritative current/next class + "does this student have an academic timetable AT ALL?":
        # one broad forward scan. This keeps an empty single day/week from being mistaken for "no
        # timetable" and wrongly replaced by the unrelated portal schedule.
        try:
            broad_rows = await academic.get_student_meetings_in_range(
                student_id=ident.student_profile_id,
                start_at=now - timedelta(hours=6),
                end_at=now + timedelta(days=120),
            )
        except Exception:
            logger.exception("get_my_schedule failed.")
            return _error("Could not read the class schedule right now.")
        broad = [_academic_meeting(r) for r in broad_rows]
        current = next(
            (m for m in broad if m["_start"] and m["_end"] and m["_start"] <= now <= m["_end"]),
            None,
        )
        nxt = next((m for m in broad if m["_start"] and m["_start"] > now), None)
        has_academic = bool(broad)

        # now/next also fall back to the stable student schedule API when the academic timetable is
        # empty, so a student with only canonical calendar data still gets a current/next class.
        if not has_academic and window in ("now", "next"):
            try:
                sched = await students.get_schedule(ident.student_profile_id, upcoming_only=False)
            except Exception:
                sched = []
            api_schedule = [_student_api_meeting(r) for r in sched]
            current = next(
                (
                    m
                    for m in api_schedule
                    if m["_start"] and m["_end"] and m["_start"] <= now <= m["_end"]
                ),
                None,
            )
            nxt = next((m for m in api_schedule if m["_start"] and m["_start"] > now), None)

        if window == "now":
            return _json(
                {
                    "window": window,
                    "now": _fmt(now),
                    "current_class": _strip_internal(current),
                    "next_class": _strip_internal(nxt),
                }
            )
        if window == "next":
            return _json({"window": window, "now": _fmt(now), "next_class": _strip_internal(nxt)})

        # Range windows: list EVERY meeting in [range_start, range_end) — past AND future within it
        # (so "lịch hôm nay" includes finished classes, and "tuần trước" returns last week's classes).
        try:
            win_rows = await academic.get_student_meetings_in_range(
                student_id=ident.student_profile_id, start_at=range_start, end_at=range_end
            )
        except Exception:
            logger.exception("get_my_schedule failed.")
            return _error("Could not read the class schedule right now.")
        meetings = [_strip_internal(_academic_meeting(r)) for r in win_rows]

        # Stable student-schedule API fallback ONLY when the student has NO academic timetable at
        # all (not merely an empty window). It is backed by the canonical student calendar table.
        source = "academic"
        if not has_academic:
            try:
                sched = await students.get_schedule(ident.student_profile_id, upcoming_only=False)
            except Exception:
                sched = []
            if sched:
                source = "student_schedule_api"
                api_schedule = [_student_api_meeting(r) for r in sched]
                meetings = [
                    _strip_internal(m)
                    for m in api_schedule
                    if m["_start"] and range_start <= m["_start"] < range_end
                ]
                nxt = nxt or next(
                    (m for m in api_schedule if m["_start"] and m["_start"] > now), None
                )

        return _json(
            {
                "window": window,
                "now": _fmt(now),
                "range_start": range_start.strftime("%Y-%m-%d") if range_start else None,
                "range_end": (range_end - timedelta(days=1)).strftime("%Y-%m-%d")
                if range_end
                else None,
                "source": source,
                "meetings": meetings,
                "current_class": _strip_internal(current),
                "next_class": _strip_internal(nxt),
            }
        )

    # ---- courses & transcript -----------------------------------------------------------------

    @tool
    async def get_my_courses() -> str:
        """Return the signed-in student's own current academic-term courses from the same academic
        read-model used by the dashboard (code, title, credits, instructor, term, status). No input. Use for
        "what courses am I taking / what am I enrolled in?". Reads the academic model so it matches
        get_my_schedule / get_my_transcript."""
        ident = _identity()
        if ident is None:
            return _json(_REFUSAL)
        try:
            record = await _academic_record(ident)
        except Exception:
            logger.exception("get_my_courses failed.")
            return _error("Could not read the enrolled courses right now.")
        if record is None:
            return _json({"found": False, "message": "No academic profile on record."})
        overview = record["overview"]
        current_term = record["current_term"]
        courses = [
            _course_payload(
                course,
                status="in_progress",
                term=current_term.get("code") if current_term else None,
            )
            for course in overview.enrolled_courses
        ]
        zero_credit_courses = [
            course for course in courses if int(course.get("credits") or 0) == 0
        ]
        return _json(
            {
                "found": True,
                "source": "academic_read_model",
                "term": current_term.get("code") if current_term else None,
                "count": len(courses),
                "credit_bearing_count": len(courses) - len(zero_credit_courses),
                "zero_credit_count": len(zero_credit_courses),
                "current_credits": sum(
                    int(course.get("credits") or 0)
                    for course in courses
                    if int(course.get("credits") or 0) > 0
                ),
                "courses": courses,
                "zero_credit_courses": zero_credit_courses,
                "instruction": (
                    "When listing enrolled courses, include zero-credit courses in courses/count, "
                    "but do not add them to current_credits. Use course_title_vi for Vietnamese "
                    "answers when it is present; use course_title for English answers."
                ),
            }
        )

    @tool
    async def get_my_transcript() -> str:
        """Return the signed-in student's own transcript: per-course grade (4.0 + letter), credits,
        pass/fail, attempt number, retake/improvement flag, and term. No input. Use for "what grade
        did I get in X / show my transcript / which courses did I fail or retake?"."""
        ident = _identity()
        if ident is None:
            return _json(_REFUSAL)
        try:
            rows = await academic.get_student_transcript(ident.student_profile_id)
        except Exception:
            logger.exception("get_my_transcript failed.")
            return _error("Could not read the transcript right now.")
        records = [
            {
                "course_code": row.get("course_code"),
                "course_name": row.get("course_name"),
                "course_name_vi": row.get("course_name_vi"),
                "credits": row.get("credits"),
                "grade_4": row.get("grade_4"),
                "letter_grade": row.get("letter_grade"),
                "passed": row.get("passed"),
                "status": row.get("status"),
                "attempt_no": row.get("attempt_no"),
                "is_improvement": row.get("is_improvement"),
                "term": row.get("term_name") or row.get("term_code"),
                "counts_for_gpa": row.get("is_gpa_counted"),
            }
            for row in rows
        ]
        return _json({"count": len(records), "transcript": records})

    @tool
    async def get_my_deadlines() -> str:
        """Return the signed-in student's own upcoming deadlines (title, kind, due date, related
        course). No input. Use for "what deadlines do I have coming up?"."""
        ident = _identity()
        if ident is None:
            return _json(_REFUSAL)
        try:
            record = await _academic_record(ident)
            rows = await students.get_deadlines(ident.student_profile_id, upcoming_only=True)
        except Exception:
            logger.exception("get_my_deadlines failed.")
            return _error("Could not read the deadlines right now.")
        if record is not None:
            current_course_codes = {course.code for course in record["overview"].enrolled_courses}
            rows = [
                row
                for row in rows
                if not row.get("course_code") or row.get("course_code") in current_course_codes
            ]
        deadlines = [
            {
                "title": row.get("title"),
                "kind": row.get("kind"),
                "due_at": _fmt(_to_vn(row.get("due_at"))),
                "course_code": row.get("course_code"),
                "course_title": row.get("course_title"),
                "course_title_vi": row.get("course_title_vi"),
            }
            for row in rows
        ]
        return _json({"count": len(deadlines), "deadlines": deadlines})

    # ---- curriculum progress, eligibility, projection -----------------------------------------

    @tool
    async def get_my_curriculum_progress() -> str:
        """Return the signed-in student's progress through their program curriculum: total required
        credits, credits earned, credits remaining, and the list of REMAINING required courses
        (curriculum courses they have not yet passed). No input. Use for "what courses do I still
        need / how far am I from finishing my program?"."""
        ident = _identity()
        if ident is None:
            return _json(_REFUSAL)
        try:
            acad_profile = await academic.get_student_profile_by_user(ident.user_id)
        except Exception:
            logger.exception("get_my_curriculum_progress failed.")
            return _error("Could not read curriculum progress right now.")
        if not acad_profile or not acad_profile.get("program_id"):
            return _json({"found": False, "message": "No program/curriculum on record."})
        try:
            transcript = await academic.get_student_transcript(ident.student_profile_id)
            curriculum = await academic.get_curriculum(acad_profile["program_id"])
        except Exception:
            logger.exception("get_my_curriculum_progress curriculum/transcript failed.")
            return _error("Could not read curriculum progress right now.")
        progress = academic_service.build_curriculum_progress(
            program=acad_profile,
            curriculum=curriculum,
            enrollments=transcript,
        )

        def item(course: Any) -> dict[str, Any]:
            return {
                "course_code": course.course.code,
                "course_name": course.course.name,
                "course_name_vi": course.course.name_vi,
                "credits": course.course.credits,
                "category": course.category,
                "is_required": course.is_required,
                "suggested_year": course.suggested_year,
                "suggested_term": course.suggested_term,
                "status": course.status,
                "grade_4": course.grade_4,
            }

        remaining = [item(course) for course in progress.remaining_required]
        remaining_zero_credit = [item(course) for course in progress.remaining_zero_credit]
        in_progress = [item(course) for course in progress.in_progress]
        failed = [item(course) for course in progress.failed]
        credits_remaining = max(
            0, int(progress.summary.required_credits) - int(progress.summary.earned_credits)
        )
        return _json(
            {
                "found": True,
                "program": acad_profile.get("program_name"),
                "total_required_credits": progress.summary.required_credits,
                "credits_earned": progress.summary.earned_credits,
                "credits_remaining": credits_remaining,
                "progress_percent": progress.summary.progress_percent,
                "completed_required_courses": progress.summary.completed_required_courses,
                "remaining_required_courses": progress.summary.remaining_required_courses,
                "in_progress_courses_count": len(in_progress),
                "in_progress_courses": in_progress,
                "failed_courses_count": len(failed),
                "failed_courses": failed,
                "remaining_courses_count": len(remaining) + len(remaining_zero_credit),
                "remaining_courses": remaining,
                "remaining_zero_credit_courses": remaining_zero_credit,
            }
        )

    @tool
    async def get_my_course_eligibility() -> str:
        """Return which of the student's REMAINING required courses they are eligible to take now
        (all prerequisites satisfied) versus blocked (and by which prerequisite). No input. Use for
        "what can I register for / what am I eligible to take next?"."""
        ident = _identity()
        if ident is None:
            return _json(_REFUSAL)
        try:
            acad_profile = await academic.get_student_profile_by_user(ident.user_id)
            if not acad_profile or not acad_profile.get("program_id"):
                return _json({"found": False, "message": "No program/curriculum on record."})
            term = await academic.get_current_term()
            curriculum = await academic.get_curriculum(acad_profile["program_id"])
            transcript = await academic.get_student_transcript(ident.student_profile_id)
        except Exception:
            logger.exception("get_my_course_eligibility failed.")
            return _error("Could not read course eligibility right now.")
        if not term:
            return _error("No current academic term is available to evaluate eligibility.")

        try:
            requisites = await academic.get_requisite_status_bulk(
                student_id=ident.student_profile_id,
                course_ids=[c["course_id"] for c in curriculum if c.get("course_id")],
                term_id=term["id"],
            )
        except Exception:
            logger.exception("get_my_course_eligibility requisites failed.")
            return _error("Could not evaluate prerequisites right now.")
        eligibility = academic_service.build_course_eligibility(
            term=term,
            curriculum=curriculum,
            enrollments=transcript,
            requisites_by_course=requisites,
        )

        def entry(course: Any) -> dict[str, Any]:
            return {
                "course_code": course.course.code,
                "course_name": course.course.name,
                "course_name_vi": course.course.name_vi,
                "credits": course.course.credits,
                "category": course.category,
                "is_required": course.is_required,
                "already_completed": course.already_completed,
                "can_retake_or_improve": course.can_retake_or_improve,
                "blocking_reasons": course.blocking_reasons,
            }

        eligible = [entry(course) for course in eligibility.eligible]
        blocked = [entry(course) for course in eligibility.blocked]
        return _json(
            {
                "found": True,
                "term": term.get("code"),
                "eligible_count": len(eligible),
                "eligible_now": eligible,
                "blocked_count": len(blocked),
                "blocked": blocked,
            }
        )

    @tool
    async def project_gpa_for_target(target_gpa: float) -> str:
        """Deterministically compute the average grade (on the 4.0 scale) the student must earn on
        their REMAINING credits to reach a target cumulative GPA, given their authoritative current
        GPA and credits. Returns the needed average and whether it is reachable (≤ 4.0).

        target_gpa: the desired cumulative GPA on the 4.0 scale. For an "Excellent" (Xuất sắc) degree
        use 3.6. Use for "what average do I need to graduate with an Excellent degree / reach GPA X?"."""
        ident = _identity()
        if ident is None:
            return _json(_REFUSAL)
        try:
            target = float(target_gpa)
        except (TypeError, ValueError):
            return _error("target_gpa must be a number on the 4.0 scale (e.g. 3.6 for Excellent).")
        try:
            record = await _academic_record(ident)
        except Exception:
            logger.exception("project_gpa_for_target failed.")
            return _error("Could not read academic standing for the projection right now.")
        if record is None:
            return _json({"found": False, "message": "No academic profile on record."})
        overview = record["overview"]
        transcript_summary = academic_service.build_transcript_summary(
            record["profile"]["id"], record["transcript"]
        )
        cpa = overview.cumulative_cpa
        credits_earned = overview.earned_credits
        gpa_credits = transcript_summary.gpa_credits
        total_required = overview.required_credits
        if cpa is None or not total_required:
            return _json(
                {
                    "found": False,
                    "message": "Not enough academic data (GPA / credits) to compute a projection.",
                }
            )
        cpa = float(cpa)
        credits_earned = int(credits_earned)
        gpa_credits = int(gpa_credits)
        total_required = int(total_required)
        credits_remaining = total_required - credits_earned
        projected_total_gpa_credits = gpa_credits + max(0, credits_remaining)

        result: dict[str, Any] = {
            "found": True,
            "target_gpa": round(target, 3),
            "current_gpa": round(cpa, 3),
            "current_cumulative_cpa": round(cpa, 3),
            "credits_earned": credits_earned,
            "gpa_credits": gpa_credits,
            "total_required_credits": total_required,
            "credits_remaining": max(0, credits_remaining),
        }
        if credits_remaining <= 0:
            result["already_completed_credits"] = True
            result["reachable"] = cpa >= target
            result["message"] = (
                "All required credits are already earned; the cumulative GPA is fixed at the current value."
            )
            return _json(result)

        needed = (target * projected_total_gpa_credits - cpa * gpa_credits) / credits_remaining
        result["needed_average_on_remaining"] = round(needed, 3)
        if needed <= 0:
            result["reachable"] = True
            result["message"] = "Already on track — even minimal passing grades keep the target reachable."
        elif needed > EXCELLENT_GPA_4:
            result["reachable"] = False
            result["message"] = (
                f"Not reachable: it would require a {round(needed, 3)} average on the remaining "
                f"{credits_remaining} credits, above the 4.0 maximum."
            )
        else:
            result["reachable"] = True
            result["message"] = (
                f"Reachable: needs about a {round(needed, 3)} average on the remaining "
                f"{credits_remaining} credits."
            )
        return _json(result)

    return [
        get_my_profile,
        get_my_academic_standing,
        get_my_schedule,
        get_my_courses,
        get_my_transcript,
        get_my_deadlines,
        get_my_curriculum_progress,
        get_my_course_eligibility,
        project_gpa_for_target,
    ]
