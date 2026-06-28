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
from vinchatbot.app.core.timeutils import VINUNI_TZ, now_in_vietnam
from vinchatbot.app.repositories.academic import AcademicRepository
from vinchatbot.app.repositories.students import StudentRepository

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

_SCHEDULE_WINDOWS = ("now", "today", "tomorrow", "this_week", "next", "all")

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
                "program": portal.get("program") or acad.get("program_name"),
                "program_code": acad.get("program_code"),
                "major": portal.get("major"),
                "degree_level": acad.get("program_degree_level"),
                "faculty": acad.get("faculty_name"),
                "institute": (portal.get("institute") or {}).get("name_en"),
                "cohort": portal.get("cohort") or acad.get("cohort_year"),
                "academic_year": portal.get("academic_year") or acad.get("current_year"),
                "advisor_name": portal.get("advisor_name"),
                "advisor_email": portal.get("advisor_email"),
                "total_required_credits": acad.get("program_total_required_credits"),
            }
        )

    @tool
    async def get_my_academic_standing() -> str:
        """Return the signed-in student's authoritative GPA, credits earned, credits required,
        academic standing/status, and current semester (read from the official academic summary —
        never recomputed). No input. Use for "what is my GPA / how many credits do I have / am I in
        good standing?"."""
        ident = _identity()
        if ident is None:
            return _json(_REFUSAL)
        try:
            portal = await students.get_current_student_profile(ident.user_id)
        except Exception:
            logger.exception("get_my_academic_standing failed.")
            return _error("Could not read the academic standing right now.")
        summary = (portal or {}).get("academic_summary")
        if not summary:
            return _json({"found": False, "message": "No academic summary on record yet."})
        return _json(
            {
                "found": True,
                "gpa": summary.get("gpa"),
                "gpa_scale": "4.0",
                "credits_earned": summary.get("credits_earned"),
                "credits_required": summary.get("credits_required"),
                "academic_status": summary.get("academic_status"),
                "current_semester": summary.get("current_semester"),
            }
        )

    # ---- schedule -----------------------------------------------------------------------------

    @tool
    async def get_my_schedule(window: str = "today") -> str:
        """Return the signed-in student's own class schedule, in VinUni local time (Asia/Ho_Chi_Minh).

        window: one of "now" (the class happening right now + the next one), "today", "tomorrow",
        "this_week" (next 7 days), "next" (just the next upcoming class), "all" (next 30 days).
        Use for "what's my next class / what classes do I have today / this week / right now?"."""
        ident = _identity()
        if ident is None:
            return _json(_REFUSAL)
        window = (window or "today").strip().lower()
        if window not in _SCHEDULE_WINDOWS:
            window = "today"

        now = now_in_vietnam()
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        if window == "today":
            start, end = day_start, day_start + timedelta(days=1)
        elif window == "tomorrow":
            start, end = day_start + timedelta(days=1), day_start + timedelta(days=2)
        elif window == "this_week":
            start, end = day_start, day_start + timedelta(days=7)
        else:  # now / next / all -> scan a broad forward window, compute in Python
            start, end = now - timedelta(hours=6), now + timedelta(days=30)

        try:
            rows = await academic.get_student_meetings_in_range(
                student_id=ident.student_profile_id, start_at=start, end_at=end
            )
        except Exception:
            logger.exception("get_my_schedule failed.")
            return _error("Could not read the class schedule right now.")

        meetings = []
        for row in rows:
            start_vn = _to_vn(row.get("start_at"))
            end_vn = _to_vn(row.get("end_at"))
            meetings.append(
                {
                    "course_code": row.get("course_code"),
                    "course_name": row.get("course_name"),
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
            )

        # Fallback to the portal schedule model if the academic timetable is empty for this student.
        if not meetings:
            try:
                sched = await students.get_schedule(ident.student_profile_id, upcoming_only=True)
            except Exception:
                sched = []
            if sched:
                fallback = []
                for row in sched:
                    start_vn = _to_vn(row.get("start_time"))
                    end_vn = _to_vn(row.get("end_time"))
                    fallback.append(
                        {
                            "course_code": row.get("course_code"),
                            "course_name": row.get("course_title"),
                            "title": row.get("title"),
                            "type": row.get("schedule_type"),
                            "start": _fmt(start_vn),
                            "end": _fmt(end_vn),
                            "room": row.get("room"),
                            "building": row.get("building"),
                            "instructor": row.get("instructor"),
                        }
                    )
                return _json({"window": window, "now": _fmt(now), "source": "portal", "meetings": fallback})
            return _json({"window": window, "now": _fmt(now), "meetings": []})

        current = None
        nxt = None
        for meeting in meetings:
            mstart, mend = meeting.get("_start"), meeting.get("_end")
            if mstart and mend and mstart <= now <= mend and current is None:
                current = meeting
            if mstart and mstart > now and nxt is None:
                nxt = meeting
        for meeting in meetings:
            meeting.pop("_start", None)
            meeting.pop("_end", None)

        if window == "now":
            return _json(
                {
                    "window": window,
                    "now": _fmt(now),
                    "current_class": current,
                    "next_class": nxt,
                }
            )
        if window == "next":
            return _json({"window": window, "now": _fmt(now), "next_class": nxt})
        return _json({"window": window, "now": _fmt(now), "meetings": meetings})

    # ---- courses & transcript -----------------------------------------------------------------

    @tool
    async def get_my_courses() -> str:
        """Return the signed-in student's own enrolled courses (code, title, credits, term,
        instructor). No input. Use for "what courses am I taking / what am I enrolled in?"."""
        ident = _identity()
        if ident is None:
            return _json(_REFUSAL)
        try:
            rows = await students.get_courses(ident.student_profile_id)
        except Exception:
            logger.exception("get_my_courses failed.")
            return _error("Could not read the enrolled courses right now.")
        courses = [
            {
                "course_code": row.get("course_code"),
                "course_title": row.get("course_title"),
                "credits": row.get("credits"),
                "semester": row.get("semester"),
                "academic_year": row.get("academic_year"),
                "instructor": row.get("instructor"),
            }
            for row in rows
        ]
        return _json({"count": len(courses), "courses": courses})

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
            rows = await students.get_deadlines(ident.student_profile_id, upcoming_only=True)
        except Exception:
            logger.exception("get_my_deadlines failed.")
            return _error("Could not read the deadlines right now.")
        deadlines = [
            {
                "title": row.get("title"),
                "kind": row.get("kind"),
                "due_at": _fmt(_to_vn(row.get("due_at"))),
                "course_code": row.get("course_code"),
                "course_title": row.get("course_title"),
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
            portal = await students.get_current_student_profile(ident.user_id)
        except Exception:
            logger.exception("get_my_curriculum_progress failed.")
            return _error("Could not read curriculum progress right now.")
        if not acad_profile or not acad_profile.get("program_id"):
            return _json({"found": False, "message": "No program/curriculum on record."})
        try:
            curriculum = await academic.get_curriculum(acad_profile["program_id"])
            transcript = await academic.get_student_transcript(ident.student_profile_id)
        except Exception:
            logger.exception("get_my_curriculum_progress curriculum/transcript failed.")
            return _error("Could not read curriculum progress right now.")

        passed_course_ids = {row.get("course_id") for row in transcript if row.get("passed")}
        remaining = [
            {
                "course_code": course.get("course_code"),
                "course_name": course.get("course_name"),
                "credits": course.get("credits"),
                "category": course.get("category"),
                "is_required": course.get("is_required"),
                "suggested_year": course.get("suggested_year"),
                "suggested_term": course.get("suggested_term"),
            }
            for course in curriculum
            if course.get("course_id") not in passed_course_ids
        ]
        summary = (portal or {}).get("academic_summary") or {}
        total_required = acad_profile.get("program_total_required_credits") or summary.get(
            "credits_required"
        )
        credits_earned = summary.get("credits_earned")
        credits_remaining = None
        if total_required is not None and credits_earned is not None:
            credits_remaining = max(0, int(total_required) - int(credits_earned))
        return _json(
            {
                "found": True,
                "program": acad_profile.get("program_name"),
                "total_required_credits": total_required,
                "credits_earned": credits_earned,
                "credits_remaining": credits_remaining,
                "remaining_courses_count": len(remaining),
                "remaining_courses": remaining,
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
            curriculum = await academic.get_curriculum(acad_profile["program_id"])
            transcript = await academic.get_student_transcript(ident.student_profile_id)
            term = await academic.get_current_term()
        except Exception:
            logger.exception("get_my_course_eligibility failed.")
            return _error("Could not read course eligibility right now.")
        if not term:
            return _error("No current academic term is available to evaluate eligibility.")

        passed_course_ids = {row.get("course_id") for row in transcript if row.get("passed")}
        remaining = [c for c in curriculum if c.get("course_id") not in passed_course_ids]
        course_ids = [c["course_id"] for c in remaining if c.get("course_id")]
        try:
            requisites = await academic.get_requisite_status_bulk(
                student_id=ident.student_profile_id,
                course_ids=course_ids,
                term_id=term["id"],
            )
        except Exception:
            logger.exception("get_my_course_eligibility requisites failed.")
            return _error("Could not evaluate prerequisites right now.")

        eligible, blocked = [], []
        for course in remaining:
            reqs = requisites.get(course.get("course_id"), [])
            unmet = [r for r in reqs if not r.get("satisfied")]
            entry = {
                "course_code": course.get("course_code"),
                "course_name": course.get("course_name"),
                "credits": course.get("credits"),
            }
            if unmet:
                entry["missing_prerequisites"] = [
                    r.get("required_course_code") for r in unmet if r.get("required_course_code")
                ]
                blocked.append(entry)
            else:
                eligible.append(entry)
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
            portal = await students.get_current_student_profile(ident.user_id)
            acad_profile = await academic.get_student_profile_by_user(ident.user_id)
        except Exception:
            logger.exception("project_gpa_for_target failed.")
            return _error("Could not read academic standing for the projection right now.")
        summary = (portal or {}).get("academic_summary") or {}
        gpa = summary.get("gpa")
        credits_earned = summary.get("credits_earned")
        total_required = (acad_profile or {}).get("program_total_required_credits") or summary.get(
            "credits_required"
        )
        if gpa is None or credits_earned is None or not total_required:
            return _json(
                {
                    "found": False,
                    "message": "Not enough academic data (GPA / credits) to compute a projection.",
                }
            )
        gpa = float(gpa)
        credits_earned = int(credits_earned)
        total_required = int(total_required)
        credits_remaining = total_required - credits_earned

        result: dict[str, Any] = {
            "found": True,
            "target_gpa": round(target, 3),
            "current_gpa": round(gpa, 3),
            "credits_earned": credits_earned,
            "total_required_credits": total_required,
            "credits_remaining": max(0, credits_remaining),
        }
        if credits_remaining <= 0:
            result["already_completed_credits"] = True
            result["reachable"] = gpa >= target
            result["message"] = (
                "All required credits are already earned; the cumulative GPA is fixed at the current value."
            )
            return _json(result)

        needed = (target * total_required - gpa * credits_earned) / credits_remaining
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
