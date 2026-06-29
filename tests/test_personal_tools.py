"""Phase 5: read-only, per-student-scoped personalization tools + personal routing.

All offline (no live DB, no network): the academic/student repositories are replaced with fakes that
record the ids they are called with and return canned rows, and the graph is exercised with injected
specialist stubs (the same pattern as test_fanout_graph.py). The live read-only enforcement
(default_transaction_read_only) and real Neon data are covered by the separate live smoke, not here.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import UTC, date, datetime

import pytest
from langchain_core.messages import AIMessage, ToolMessage
from langgraph.checkpoint.memory import InMemorySaver

from vinchatbot.app.agents import personal_tools as pt
from vinchatbot.app.agents.graph import FANOUT_ROUTE, build_agent_graph
from vinchatbot.app.agents.specialists import PERSONAL_INTENT
from vinchatbot.app.agents.supervisor import INTENTS
from vinchatbot.app.core.observability import reset_student_identity, set_student_identity
from vinchatbot.app.core.timeutils import VINUNI_TZ

USER_A = uuid.uuid4()
PROFILE_A = uuid.uuid4()
FACULTY_ID = uuid.uuid4()
PROGRAM_ID = uuid.uuid4()
TERM_ID = uuid.uuid4()
COURSE_1010 = uuid.uuid4()
COURSE_2020 = uuid.uuid4()


# --- fakes ----------------------------------------------------------------------------------------

class FakeStudentRepo:
    last_user_id = None
    last_profile_id = None

    def __init__(self, pool):
        self.pool = pool

    async def get_current_student_profile(self, user_id):
        FakeStudentRepo.last_user_id = user_id
        return {
            "program": "Computer Science",
            "major": "CS",
            "advisor_name": "Dr. Advisor",
            "advisor_email": "advisor@vinuni.edu.vn",
            "cohort": 2024,
            "academic_year": "2025-2026",
            "institute": {"name_en": "College of Engineering & Computer Science"},
            "academic_summary": {
                "gpa": 3.0,
                "credits_earned": 60,
                "credits_required": 120,
                "academic_status": "good_standing",
                "current_semester": "2026-SUMMER",
            },
        }

    async def get_courses(self, student_profile_id):
        FakeStudentRepo.last_profile_id = student_profile_id
        return [
            {
                "course_code": "COMP1010",
                "course_title": "Intro to CS",
                "credits": 4,
                "semester": "Summer",
                "academic_year": "2025-2026",
                "instructor": "Prof X",
            }
        ]

    async def get_schedule(self, student_profile_id, *, upcoming_only=True):
        FakeStudentRepo.last_profile_id = student_profile_id
        return []

    async def get_deadlines(self, student_profile_id, *, upcoming_only=True):
        FakeStudentRepo.last_profile_id = student_profile_id
        return [
            {
                "title": "Project 1",
                "kind": "assignment",
                "due_at": datetime(2026, 7, 1, 3, 0, tzinfo=UTC),
                "course_code": "COMP1010",
                "course_title": "Intro to CS",
            }
        ]


class FakeAcademicRepo:
    last_user_id = None
    last_student_id = None
    meetings: list = []

    def __init__(self, pool):
        self.pool = pool

    async def get_student_profile_by_user(self, user_id):
        FakeAcademicRepo.last_user_id = user_id
        return {
            "id": PROFILE_A,
            "user_id": user_id,
            "student_code": "V202400123",
            "full_name": "Demo Student",
            "faculty_id": FACULTY_ID,
            "faculty_code": "CECS",
            "faculty_name": "CECS",
            "program_id": PROGRAM_ID,
            "program_name": "Computer Science",
            "program_code": "CS",
            "program_degree_level": "bachelor",
            "program_curriculum_year": 2026,
            "cohort_year": 2024,
            "current_year": 2,
            "status": "active",
            "program_total_required_credits": 120,
        }

    async def get_student_transcript(self, student_id):
        FakeAcademicRepo.last_student_id = student_id
        return [
            {
                "id": uuid.uuid4(),
                "student_id": student_id,
                "course_code": "COMP1010",
                "course_name": "Intro to CS",
                "credits": 60,
                "grade_10": 7.0,
                "grade_4": 3.0,
                "letter_grade": "B",
                "passed": True,
                "status": "completed",
                "attempt_no": 1,
                "is_improvement": False,
                "retake_of_enrollment_id": None,
                "term_name": "Spring 2025",
                "term_id": TERM_ID,
                "term_code": "2026-SUMMER",
                "start_date": date(2026, 6, 1),
                "end_date": date(2026, 7, 31),
                "academic_year": 2026,
                "term_order": 3,
                "is_gpa_counted": True,
                "earned_credits": 60,
                "completed_at": datetime(2026, 6, 20, tzinfo=UTC),
                "course_id": COURSE_1010,
                "course_level": 101,
                "department_code": "COMP",
                "is_general_education": False,
                "section_id": None,
                "section_code": None,
            },
            {
                "id": uuid.uuid4(),
                "student_id": student_id,
                "course_code": "COMP2020",
                "course_name": "Data Structures",
                "credits": 4,
                "grade_10": None,
                "grade_4": None,
                "letter_grade": None,
                "passed": False,
                "status": "enrolled",
                "attempt_no": 1,
                "is_improvement": False,
                "retake_of_enrollment_id": None,
                "term_name": "Summer 2026",
                "term_id": TERM_ID,
                "term_code": "2026-SUMMER",
                "start_date": date(2026, 6, 1),
                "end_date": date(2026, 7, 31),
                "academic_year": 2026,
                "term_order": 3,
                "is_gpa_counted": False,
                "earned_credits": 0,
                "completed_at": None,
                "course_id": COURSE_2020,
                "course_level": 202,
                "department_code": "COMP",
                "is_general_education": False,
                "section_id": uuid.uuid4(),
                "section_code": "A",
            },
        ]

    async def get_student_meetings_in_range(self, *, student_id, start_at, end_at):
        FakeAcademicRepo.last_student_id = student_id
        return list(FakeAcademicRepo.meetings)

    async def get_curriculum(self, program_id):
        return [
            {"course_id": COURSE_1010, "course_code": "COMP1010", "course_name": "Intro to CS",
             "credits": 60, "category": "major_core", "is_required": True, "suggested_year": 1,
             "suggested_term": 1, "course_level": 101, "department_code": "COMP",
             "is_general_education": False, "description": None},
            {"course_id": COURSE_2020, "course_code": "COMP2020", "course_name": "Data Structures",
             "credits": 4, "category": "major_core", "is_required": True, "suggested_year": 1,
             "suggested_term": 2, "course_level": 202, "department_code": "COMP",
             "is_general_education": False, "description": None},
        ]

    async def get_requisite_status_bulk(self, *, student_id, course_ids, term_id):
        return {}

    async def get_current_term(self):
        return {
            "id": TERM_ID,
            "code": "2026-SUMMER",
            "name": "Summer Term 2026",
            "start_date": date(2026, 6, 1),
            "end_date": date(2026, 7, 31),
            "academic_year": 2026,
            "term_order": 3,
        }


@pytest.fixture
def tools(monkeypatch):
    monkeypatch.setattr(pt, "StudentRepository", FakeStudentRepo)
    monkeypatch.setattr(pt, "AcademicRepository", FakeAcademicRepo)
    FakeStudentRepo.last_user_id = FakeStudentRepo.last_profile_id = None
    FakeAcademicRepo.last_user_id = FakeAcademicRepo.last_student_id = None
    FakeAcademicRepo.meetings = []
    built = pt.build_personal_tools(pool=object())
    return {t.name: t for t in built}


def _call(tool, payload=None):
    return json.loads(asyncio.run(tool.ainvoke(payload or {})))


# --- isolation: the security core -----------------------------------------------------------------

def test_no_tool_exposes_a_student_or_user_id_parameter(tools):
    # The LLM must have NO way to name a student/user — the id comes ONLY from the contextvar.
    banned = ("student", "user", "_id", "profile", "uid")
    for name, tool in tools.items():
        for arg in tool.args:
            assert not any(token in arg.lower() for token in banned), f"{name}.{arg} leaks an id param"


def test_tools_scope_queries_to_the_session_identity_only(tools):
    set_student_identity(student_profile_id=PROFILE_A, user_id=USER_A)
    try:
        standing = _call(tools["get_my_academic_standing"])
        assert standing["found"] is True and standing["gpa"] == 3.0
        assert standing["cumulative_cpa"] == 3.0
        # the read used the session's user id, nothing the model supplied
        assert FakeAcademicRepo.last_user_id == USER_A

        transcript = _call(tools["get_my_transcript"])
        assert transcript["count"] == 2
        # transcript keyed by the session's student_profile_id
        assert FakeAcademicRepo.last_student_id == PROFILE_A
    finally:
        reset_student_identity()


def test_every_tool_refuses_without_a_signed_in_identity(tools):
    reset_student_identity()  # anonymous / admin / no session
    inputs = {"get_my_schedule": {"window": "today"}, "project_gpa_for_target": {"target_gpa": 3.6}}
    for name, tool in tools.items():
        result = _call(tool, inputs.get(name))
        assert result.get("error") == "not_signed_in", f"{name} did not refuse for an anon caller"
    # and no repository read was attempted for the refused calls
    assert FakeStudentRepo.last_user_id is None
    assert FakeAcademicRepo.last_user_id is None and FakeAcademicRepo.last_student_id is None


# --- projection math (deterministic, no LLM) ------------------------------------------------------

def test_gpa_projection_reachable_target(tools):
    set_student_identity(student_profile_id=PROFILE_A, user_id=USER_A)
    try:
        # CPA 3.0 over 60 GPA credits; 60 remaining credits → need 3.6 to reach 3.3.
        result = _call(tools["project_gpa_for_target"], {"target_gpa": 3.3})
        assert result["found"] is True
        assert result["needed_average_on_remaining"] == 3.6
        assert result["reachable"] is True
        assert result["credits_remaining"] == 60
    finally:
        reset_student_identity()


def test_gpa_projection_infeasible_target(tools):
    set_student_identity(student_profile_id=PROFILE_A, user_id=USER_A)
    try:
        # Excellent (3.6): (3.6*120 - 3.0*60)/60 = 4.2 > 4.0 → not reachable.
        result = _call(tools["project_gpa_for_target"], {"target_gpa": 3.6})
        assert result["needed_average_on_remaining"] == 4.2
        assert result["reachable"] is False
    finally:
        reset_student_identity()


def test_courses_come_from_current_academic_enrollments_not_legacy_portal(tools):
    set_student_identity(student_profile_id=PROFILE_A, user_id=USER_A)
    try:
        result = _call(tools["get_my_courses"])
        assert result["source"] == "academic_read_model"
        assert result["term"] == "2026-SUMMER"
        assert [course["course_code"] for course in result["courses"]] == ["COMP2020"]
        assert FakeStudentRepo.last_profile_id is None
    finally:
        reset_student_identity()


# --- schedule timezone + current/next class logic -------------------------------------------------

def test_schedule_converts_utc_to_vietnam_and_picks_current_and_next(tools, monkeypatch):
    # Freeze "now" to 09:30 VN on 2026-06-29.
    fixed_now = datetime(2026, 6, 29, 9, 30, tzinfo=VINUNI_TZ)
    monkeypatch.setattr(pt, "now_in_vietnam", lambda: fixed_now)
    # A class 02:00–03:00 UTC = 09:00–10:00 VN (happening now), and 06:00 UTC = 13:00 VN (the next).
    FakeAcademicRepo.meetings = [
        {"course_code": "COMP1010", "course_name": "Intro to CS", "title": "Lecture",
         "meeting_type": "lecture", "start_at": datetime(2026, 6, 29, 2, 0, tzinfo=UTC),
         "end_at": datetime(2026, 6, 29, 3, 0, tzinfo=UTC), "section_code": "S1",
         "instructor_name": "Prof X", "room_name": "R101", "building": "B1"},
        {"course_code": "COMP2020", "course_name": "Data Structures", "title": "Lab",
         "meeting_type": "lab", "start_at": datetime(2026, 6, 29, 6, 0, tzinfo=UTC),
         "end_at": datetime(2026, 6, 29, 7, 0, tzinfo=UTC), "section_code": "S2",
         "instructor_name": "Prof Y", "room_name": "R202", "building": "B2"},
    ]
    set_student_identity(student_profile_id=PROFILE_A, user_id=USER_A)
    try:
        result = _call(tools["get_my_schedule"], {"window": "now"})
        assert result["current_class"]["start"] == "2026-06-29 09:00"  # UTC 02:00 → VN 09:00
        assert result["current_class"]["course_code"] == "COMP1010"
        assert result["next_class"]["start"] == "2026-06-29 13:00"  # UTC 06:00 → VN 13:00
        assert result["next_class"]["course_code"] == "COMP2020"
    finally:
        reset_student_identity()


# --- routing: personal vs hybrid vs general, gated on identity ------------------------------------

def _personal_specialist(name: str, record: dict):
    class _Agent:
        async def ainvoke(self, payload, config=None):
            record[name] = True
            tool = ToolMessage(content=f"ev-{name}", tool_call_id=f"{name}-1")
            return {"messages": [*payload["messages"], tool, AIMessage(content=f"answer from {name}")]}

    return _Agent()


class _SynthModel:
    async def ainvoke(self, messages, config=None):
        last = messages[-1]
        content = last["content"] if isinstance(last, dict) else getattr(last, "content", "")
        return AIMessage(content="MERGED:: " + content)


def _graph_with_personal(record):
    specialists = {intent: _personal_specialist(intent, record) for intent in INTENTS}
    specialists[PERSONAL_INTENT] = _personal_specialist(PERSONAL_INTENT, record)

    async def router(_text):
        return "services"

    return build_agent_graph(
        retriever=None,
        specialists=specialists,
        supervisor_router=router,
        model=_SynthModel(),
        checkpointer=InMemorySaver(),
    )


def _invoke(graph, text, thread):
    return asyncio.run(
        graph.ainvoke(
            {"messages": [{"role": "user", "content": text}]},
            config={"configurable": {"thread_id": thread}},
        )
    )


def test_personal_scope_routes_to_personal_for_signed_in_student():
    record: dict = {}
    set_student_identity(student_profile_id=PROFILE_A, user_id=USER_A)
    try:
        out = _invoke(_graph_with_personal(record), "What is my GPA?", "p1")
    finally:
        reset_student_identity()
    assert out["intent"] == PERSONAL_INTENT
    assert record.get(PERSONAL_INTENT) is True


def test_hybrid_scope_fans_out_personal_plus_general():
    record: dict = {}
    set_student_identity(student_profile_id=PROFILE_A, user_id=USER_A)
    try:
        # personal pronoun + policy term (scholarship) → hybrid
        out = _invoke(_graph_with_personal(record), "Tôi có đủ điều kiện học bổng không?", "p2")
    finally:
        reset_student_identity()
    assert out["intent"] == FANOUT_ROUTE
    assert record.get(PERSONAL_INTENT) is True  # the personal subtask ran


def test_general_scope_never_routes_to_personal_even_when_signed_in():
    record: dict = {}
    set_student_identity(student_profile_id=PROFILE_A, user_id=USER_A)
    try:
        out = _invoke(_graph_with_personal(record), "Học phí chương trình Khoa học máy tính là bao nhiêu?", "p3")
    finally:
        reset_student_identity()
    assert out["intent"] == "services"  # fell through to the injected general router
    assert PERSONAL_INTENT not in record  # the personal specialist never ran


def test_anonymous_caller_never_routes_to_personal():
    record: dict = {}
    reset_student_identity()  # no signed-in student
    out = _invoke(_graph_with_personal(record), "What is my GPA?", "p4")
    assert out["intent"] == "services"  # personal intercept skipped; general router used
    assert PERSONAL_INTENT not in record


def test_personal_disabled_when_no_personal_specialist_built():
    # No "personal" specialist in the graph (no DB pool at build) → personal routing fully disabled.
    record: dict = {}
    specialists = {intent: _personal_specialist(intent, record) for intent in INTENTS}

    async def router(_text):
        return "services"

    graph = build_agent_graph(
        retriever=None, specialists=specialists, supervisor_router=router, checkpointer=InMemorySaver()
    )
    set_student_identity(student_profile_id=PROFILE_A, user_id=USER_A)
    try:
        out = _invoke(graph, "What is my GPA?", "p5")
    finally:
        reset_student_identity()
    assert out["intent"] == "services"
    assert PERSONAL_INTENT not in record
