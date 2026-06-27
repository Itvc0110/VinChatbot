from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from vinchatbot.app.api.routes_academic import get_academic_repository
from vinchatbot.app.api.routes_academic import router as academic_router
from vinchatbot.app.dependencies.auth import get_current_user
from vinchatbot.app.repositories.auth import AuthenticatedUser

STUDENT_USER_ID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
ADMIN_USER_ID = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
PROFILE_ID = uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
FACULTY_ID = uuid.UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")
PROGRAM_ID = uuid.UUID("eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee")

TERM_FALL = uuid.UUID("f0000000-0000-0000-0000-000000000001")
TERM_SPRING = uuid.UUID("f0000000-0000-0000-0000-000000000002")
TERM_SUMMER = uuid.UUID("f0000000-0000-0000-0000-000000000003")


def cid(code: str) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"course:{code}")


def _run(awaitable):
    return asyncio.run(asyncio.wait_for(awaitable, timeout=3.0))


def _student_user() -> AuthenticatedUser:
    return AuthenticatedUser(
        id=STUDENT_USER_ID,
        email="student.cs.demo@vinuni.edu.vn",
        full_name="Demo CS Student",
        preferred_name="CS Student",
        status="active",
        roles=("student",),
    )


def _admin_user() -> AuthenticatedUser:
    return AuthenticatedUser(
        id=ADMIN_USER_ID,
        email="admin.global.demo@vinuni.edu.vn",
        full_name="Demo Admin",
        preferred_name="Admin",
        status="active",
        roles=("global_admin",),
    )


_TERMS = {
    TERM_FALL: {
        "term_id": TERM_FALL,
        "term_code": "2025-FALL",
        "term_name": "Fall Term 2025",
        "start_date": date(2025, 9, 1),
        "end_date": date(2025, 12, 20),
        "academic_year": 2025,
        "term_order": 1,
    },
    TERM_SPRING: {
        "term_id": TERM_SPRING,
        "term_code": "2026-SPRING",
        "term_name": "Spring Term 2026",
        "start_date": date(2026, 1, 12),
        "end_date": date(2026, 5, 15),
        "academic_year": 2026,
        "term_order": 2,
    },
    TERM_SUMMER: {
        "term_id": TERM_SUMMER,
        "term_code": "2026-SUMMER",
        "term_name": "Summer Term 2026",
        "start_date": date(2026, 6, 1),
        "end_date": date(2026, 7, 31),
        "academic_year": 2026,
        "term_order": 3,
    },
}


def _enrollment(code, credits, *, term_id, status, grade_4, passed, is_gpa_counted, earned):
    return {
        "id": uuid.uuid5(uuid.NAMESPACE_URL, f"enr:{code}:{term_id}"),
        "student_id": PROFILE_ID,
        "course_id": cid(code),
        "course_code": code,
        "course_name": f"{code} course",
        "credits": credits,
        "course_level": 100,
        "department_code": code[:3],
        "is_general_education": code.startswith("GEN"),
        "section_id": None,
        "section_code": None,
        "status": status,
        "attempt_no": 1,
        "is_improvement": False,
        "retake_of_enrollment_id": None,
        "grade_10": None,
        "grade_4": Decimal(str(grade_4)) if grade_4 is not None else None,
        "letter_grade": None,
        "passed": passed,
        "earned_credits": earned,
        "is_gpa_counted": is_gpa_counted,
        "completed_at": None,
        **_TERMS[term_id],
    }


def _curriculum_row(code, credits, *, category="major_core", is_required=True):
    return {
        "id": uuid.uuid5(uuid.NAMESPACE_URL, f"cc:{code}"),
        "program_id": PROGRAM_ID,
        "category": category,
        "is_required": is_required,
        "suggested_year": 1,
        "suggested_term": 1,
        "min_required_grade_4": None,
        "course_id": cid(code),
        "course_code": code,
        "course_name": f"{code} course",
        "credits": credits,
        "course_level": 100,
        "department_code": code[:3],
        "is_general_education": code.startswith("GEN"),
        "description": None,
    }


def _meeting(code, title, start_at, *, section="A1", room="A101", building="Building A"):
    return {
        "id": uuid.uuid5(uuid.NAMESPACE_URL, f"cm:{code}:{title}:{start_at.isoformat()}"),
        "section_id": uuid.uuid5(uuid.NAMESPACE_URL, f"sec:{code}"),
        "title": title,
        "meeting_type": "lecture",
        "start_at": start_at,
        "end_at": start_at,
        "note": None,
        "section_code": section,
        "instructor_name": "Dr. Demo",
        "course_code": code,
        "course_name": f"{code} course",
        "room_id": uuid.uuid5(uuid.NAMESPACE_URL, f"room:{room}"),
        "building": building,
        "room_name": room,
        "room_capacity": 40,
    }


class FakeAcademicRepository:
    def __init__(self, *, has_profile: bool = True):
        self.has_profile = has_profile
        self.enrollments = [
            _enrollment("MATH101", 3, term_id=TERM_FALL, status="completed", grade_4=3.0,
                        passed=True, is_gpa_counted=True, earned=3),
            _enrollment("GEN101", 2, term_id=TERM_FALL, status="completed", grade_4=4.0,
                        passed=True, is_gpa_counted=True, earned=2),
            _enrollment("PE101", 0, term_id=TERM_FALL, status="completed", grade_4=None,
                        passed=True, is_gpa_counted=False, earned=0),
            _enrollment("CS201", 3, term_id=TERM_SPRING, status="failed", grade_4=0.0,
                        passed=False, is_gpa_counted=True, earned=0),
            _enrollment("CS202", 3, term_id=TERM_SUMMER, status="enrolled", grade_4=None,
                        passed=False, is_gpa_counted=False, earned=0),
        ]
        self.curriculum = [
            _curriculum_row("MATH101", 3),
            _curriculum_row("GEN101", 2, category="general_education"),
            _curriculum_row("PE101", 0, category="physical_education"),
            _curriculum_row("CS201", 3),
            _curriculum_row("CS202", 3),
            _curriculum_row("MATH102", 3),
            _curriculum_row("CS301", 3),
            _curriculum_row("PE102", 0, category="physical_education"),
        ]
        self.meetings = [
            _meeting("CS202", "Lecture 1", datetime(2026, 6, 3, 9, 0, tzinfo=UTC)),
            _meeting("CS202", "Lecture 2", datetime(2026, 7, 10, 10, 0, tzinfo=UTC)),
        ]

    async def get_student_profile_by_user(self, user_id):
        if not self.has_profile or user_id != STUDENT_USER_ID:
            return None
        return {
            "id": PROFILE_ID,
            "user_id": STUDENT_USER_ID,
            "student_code": "S2025CS001",
            "full_name": "Demo CS Student",
            "current_year": 1,
            "cohort_year": 2025,
            "status": "active",
            "faculty_id": FACULTY_ID,
            "faculty_code": "CECS",
            "faculty_name": "College of Engineering and Computer Science",
            "program_id": PROGRAM_ID,
            "program_code": "CS",
            "program_name": "BS Computer Science",
            "program_degree_level": "bachelor",
            "program_curriculum_year": 2026,
            "program_total_required_credits": 12,
        }

    async def get_current_term(self, *, on_date=None):
        # Standalone academic_terms row shape (id/code/name/...), as the real repository returns.
        return {
            "id": TERM_SUMMER,
            "code": "2026-SUMMER",
            "name": "Summer Term 2026",
            "start_date": date(2026, 6, 1),
            "end_date": date(2026, 7, 31),
            "academic_year": 2026,
            "term_order": 3,
        }

    async def get_student_transcript(self, student_id):
        assert student_id == PROFILE_ID
        return list(self.enrollments)

    async def get_curriculum(self, program_id):
        assert program_id == PROGRAM_ID
        return list(self.curriculum)

    async def get_student_meetings_in_range(self, *, student_id, start_at, end_at):
        assert student_id == PROFILE_ID
        return [m for m in self.meetings if start_at <= m["start_at"] < end_at]

    async def get_requisite_status_bulk(self, *, student_id, course_ids, term_id):
        assert student_id == PROFILE_ID
        grouped: dict[uuid.UUID, list[dict]] = {}
        # MATH102 needs MATH101 (passed) -> satisfied.
        grouped[cid("MATH102")] = [
            {
                "course_id": cid("MATH102"),
                "required_course_id": cid("MATH101"),
                "required_course_code": "MATH101",
                "required_course_name": "MATH101 course",
                "required_course_credits": 3,
                "requisite_type": "prerequisite",
                "min_grade_4": None,
                "satisfied": True,
            }
        ]
        # CS301 needs CS201 (failed -> not passed) -> NOT satisfied (blocked).
        grouped[cid("CS301")] = [
            {
                "course_id": cid("CS301"),
                "required_course_id": cid("CS201"),
                "required_course_code": "CS201",
                "required_course_name": "CS201 course",
                "required_course_credits": 3,
                "requisite_type": "prerequisite",
                "min_grade_4": None,
                "satisfied": False,
            }
        ]
        return {c: grouped.get(c, []) for c in course_ids}


def _app(*, current_user=None, repository=None) -> FastAPI:
    app = FastAPI()
    app.include_router(academic_router)
    if current_user is not None:

        async def fake_current_user():
            return current_user

        app.dependency_overrides[get_current_user] = fake_current_user
    if repository is not None:

        async def fake_repo():
            return repository

        app.dependency_overrides[get_academic_repository] = fake_repo
    return app


async def _get(path: str, app: FastAPI):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.get(path)


# --- auth / identity -------------------------------------------------------


def test_academic_me_requires_auth():
    assert _run(_get("/academic/me", _app(repository=FakeAcademicRepository()))).status_code == 401


def test_academic_me_rejects_non_student():
    response = _run(
        _get("/academic/me", _app(current_user=_admin_user(), repository=FakeAcademicRepository()))
    )
    assert response.status_code == 403


def test_academic_me_returns_404_when_no_profile():
    response = _run(
        _get(
            "/academic/me",
            _app(current_user=_student_user(), repository=FakeAcademicRepository(has_profile=False)),
        )
    )
    assert response.status_code == 404


# --- /academic/me overview -------------------------------------------------


def test_academic_me_overview_binds_to_current_user_and_computes_gpa_cpa():
    app = _app(current_user=_student_user(), repository=FakeAcademicRepository())
    response = _run(_get("/academic/me", app))
    body = response.json()

    assert response.status_code == 200
    assert body["profile"]["id"] == str(PROFILE_ID)
    assert body["profile"]["faculty"]["code"] == "CECS"
    assert body["profile"]["program"]["code"] == "CS"
    assert body["current_term"]["code"] == "2026-SUMMER"
    # CPA across counted rows incl. the failed course: 17/8 = 2.13.
    assert body["cumulative_cpa"] == "2.13"
    assert body["earned_credits"] == 5
    assert body["required_credits"] == 12
    # Failed CS201 surfaces; currently-enrolled CS202 surfaces as enrolled (not failed).
    assert [c["code"] for c in body["failed_courses"]] == ["CS201"]
    assert [c["code"] for c in body["enrolled_courses"]] == ["CS202"]
    assert body["summary"]["completed_required_courses"] == 3
    assert body["summary"]["remaining_required_courses"] == 5


# --- transcript ------------------------------------------------------------


def test_academic_me_transcript_groups_by_term():
    app = _app(current_user=_student_user(), repository=FakeAcademicRepository())
    body = _run(_get("/academic/me/transcript", app)).json()

    assert body["student_id"] == str(PROFILE_ID)
    assert [t["term"]["code"] for t in body["terms"]] == ["2025-FALL", "2026-SPRING", "2026-SUMMER"]
    fall = body["terms"][0]
    assert fall["term_gpa"] == "3.40"
    assert {e["course"]["code"] for e in fall["enrollments"]} == {"MATH101", "GEN101", "PE101"}
    assert body["summary"]["earned_credits"] == 5


# --- curriculum ------------------------------------------------------------


def test_academic_me_curriculum_buckets_courses():
    app = _app(current_user=_student_user(), repository=FakeAcademicRepository())
    body = _run(_get("/academic/me/curriculum", app)).json()

    assert body["program"]["code"] == "CS"
    assert {c["course"]["code"] for c in body["completed"]} == {"MATH101", "GEN101", "PE101"}
    assert {c["course"]["code"] for c in body["in_progress"]} == {"CS202"}
    assert {c["course"]["code"] for c in body["failed"]} == {"CS201"}
    # Remaining required (credit-bearing) vs remaining 0-credit requirement.
    assert {c["course"]["code"] for c in body["remaining_required"]} == {"MATH102", "CS301"}
    assert {c["course"]["code"] for c in body["remaining_zero_credit"]} == {"PE102"}
    assert body["summary"]["earned_credits"] == 5
    assert body["summary"]["required_credits"] == 12


# --- eligibility -----------------------------------------------------------


def test_academic_me_eligible_courses_explains_prerequisites():
    app = _app(current_user=_student_user(), repository=FakeAcademicRepository())
    body = _run(_get("/academic/me/courses/eligible", app)).json()

    assert body["term"]["code"] == "2026-SUMMER"
    eligible_codes = {c["course"]["code"] for c in body["eligible"]}
    blocked_codes = {c["course"]["code"] for c in body["blocked"]}

    # MATH102's prerequisite (MATH101) is satisfied -> eligible.
    assert "MATH102" in eligible_codes
    # CS301 is blocked because its prerequisite CS201 was failed.
    assert "CS301" in blocked_codes
    # The currently-enrolled course is excluded from both lists.
    assert "CS202" not in eligible_codes and "CS202" not in blocked_codes

    cs301 = next(c for c in body["blocked"] if c["course"]["code"] == "CS301")
    assert cs301["eligible"] is False
    assert any("CS201" in reason for reason in cs301["blocking_reasons"])
    assert cs301["prerequisites"][0]["required_course"]["code"] == "CS201"
    assert cs301["prerequisites"][0]["satisfied"] is False

    # The failed course can be retaken.
    cs201 = next((c for c in body["eligible"] if c["course"]["code"] == "CS201"), None)
    assert cs201 is not None and cs201["can_retake_or_improve"] is True


# --- schedule --------------------------------------------------------------


def test_schedule_me_filters_by_month():
    app = _app(current_user=_student_user(), repository=FakeAcademicRepository())

    june = _run(_get("/schedule/me?month=2026-06", app)).json()
    july = _run(_get("/schedule/me?month=2026-07", app)).json()

    assert [e["title"] for e in june] == ["Lecture 1"]
    assert [e["title"] for e in july] == ["Lecture 2"]
    assert june[0]["course_code"] == "CS202"
    assert june[0]["instructor_name"] == "Dr. Demo"
    assert june[0]["room_name"] == "A101"


def test_schedule_me_rejects_bad_month():
    app = _app(current_user=_student_user(), repository=FakeAcademicRepository())
    assert _run(_get("/schedule/me?month=2026-13", app)).status_code == 422
    assert _run(_get("/schedule/me?month=June", app)).status_code == 422


def test_schedule_me_requires_auth():
    assert _run(
        _get("/schedule/me?month=2026-06", _app(repository=FakeAcademicRepository()))
    ).status_code == 401
