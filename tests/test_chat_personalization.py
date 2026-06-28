from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

import vinchatbot.app.agents.vinuni_agent as agent_mod
from vinchatbot.app.api import routes_chat
from vinchatbot.app.core.config import get_settings
from vinchatbot.app.core.observability import reset_student_identity, set_student_identity
from vinchatbot.app.repositories.auth import AuthenticatedUser
from vinchatbot.app.schemas.chat import ChatRequest, ChatResponse
from vinchatbot.app.schemas.personalization import (
    PersonalizationAcademicSummary,
    PersonalizationContext,
    PersonalizationCourse,
    PersonalizationInstitute,
    PersonalizationStudentProfile,
)

STUDENT_USER_ID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
ADMIN_USER_ID = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
PROFILE_ID = uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
INSTITUTE_ID = uuid.UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")
NEW_CONVERSATION_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
NOW = datetime(2026, 10, 1, tzinfo=UTC)


def _run(awaitable):
    return asyncio.run(asyncio.wait_for(awaitable, timeout=2.0))


def _student_user() -> AuthenticatedUser:
    return AuthenticatedUser(
        id=STUDENT_USER_ID,
        email="student.cs.demo@vinuni.edu.vn",
        full_name="Demo CECS Student",
        preferred_name="CECS Student",
        status="active",
        roles=("student",),
    )


def _admin_user() -> AuthenticatedUser:
    return AuthenticatedUser(
        id=ADMIN_USER_ID,
        email="admin.global.demo@vinuni.edu.vn",
        full_name="Demo Global Admin",
        preferred_name="Global Admin",
        status="active",
        roles=("global_admin",),
    )


def _context(*, ai_enabled: bool = True) -> PersonalizationContext:
    return PersonalizationContext(
        profile=PersonalizationStudentProfile(
            id=PROFILE_ID,
            student_id="D2026CECS001",
            program="Bachelor of Computer Science",
            major="Computer Science",
            cohort=2026,
            academic_year=1,
            preferred_language="en",
            ai_personalization_enabled=ai_enabled,
            institute=PersonalizationInstitute(
                id=INSTITUTE_ID,
                code="CECS",
                name_vi="Viện Kỹ thuật và Khoa học Máy tính",
                name_en="College of Engineering and Computer Science",
            ),
            academic_summary=PersonalizationAcademicSummary(
                gpa=Decimal("3.40"),
                credits_earned=36,
                credits_required=120,
                current_semester="Fall 2026",
                academic_status="normal",
            ),
        ),
        courses=[
            PersonalizationCourse(
                id=uuid.UUID("eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee"),
                course_code="CSC202",
                course_title="Data Structures and Algorithms",
                semester="Fall 2026",
                academic_year="2026-2027",
                instructor="Tuan Nguyen",
            )
        ],
    )


class FakePersonalizationRepository:
    def __init__(self, context: PersonalizationContext | None) -> None:
        self.context = context
        self.calls: list[uuid.UUID] = []

    async def get_context(self, user_id: uuid.UUID) -> PersonalizationContext | None:
        self.calls.append(user_id)
        return self.context


class FakeConversationRepository:
    def __init__(self) -> None:
        self.appended: list[dict[str, Any]] = []

    async def create_conversation(self, *, user_id, request):
        return {
            "id": NEW_CONVERSATION_ID,
            "title": "New conversation",
            "title_manual": False,
            "topic": request.topic,
            "created_at": NOW,
            "updated_at": NOW,
            "last_message_at": None,
            "messages": [],
        }

    async def append_message(self, *, user_id, conversation_id, request):
        row = {
            "id": uuid.uuid5(uuid.NAMESPACE_URL, f"{len(self.appended)}:{request.role}"),
            "user_id": user_id,
            "conversation_id": conversation_id,
            "role": request.role,
            "content": request.content,
            "answer_json": request.answer_json,
            "confidence": request.confidence,
            "needs_human_review": request.needs_human_review,
            "created_at": NOW,
        }
        self.appended.append(row)
        return row


def _capturing_resolver(captured: dict[str, Any]):
    async def _resolve(request: ChatRequest) -> ChatResponse:
        captured["message"] = request.message
        captured["personalization"] = request.backend_personalization_context
        return ChatResponse(answer="Personalized answer.", confidence=0.9)

    return _resolve


def test_authenticated_student_chat_builds_personalization_context(monkeypatch):
    captured: dict[str, Any] = {}
    monkeypatch.setattr(routes_chat, "_resolve_chat", _capturing_resolver(captured))
    conversation_repo = FakeConversationRepository()
    personalization_repo = FakePersonalizationRepository(_context())

    response = _run(
        routes_chat.chat(
            ChatRequest(message="When is my next class?"),
            current_user=_student_user(),
            conversation_repository=conversation_repo,
            personalization_repository=personalization_repo,
        )
    )

    assert response.answer == "Personalized answer."
    # Context was built server-side for this student and attached to the agent input.
    assert personalization_repo.calls == [STUDENT_USER_ID]
    assert captured["personalization"] is not None
    assert "CSC202" in captured["personalization"]
    # The raw question reaches the agent unchanged (no hidden prepended block).
    assert captured["message"] == "When is my next class?"
    # Persistence stores the ORIGINAL question, not an expanded personalization prompt.
    user_messages = [row for row in conversation_repo.appended if row["role"] == "user"]
    assert user_messages[0]["content"] == "When is my next class?"
    assert "Student profile" not in user_messages[0]["content"]


def test_authenticated_student_stream_builds_personalization_context(monkeypatch):
    captured: dict[str, Any] = {}
    monkeypatch.setattr(routes_chat, "_resolve_chat", _capturing_resolver(captured))
    monkeypatch.setattr(routes_chat, "_answer_chunks", lambda answer: [answer])
    conversation_repo = FakeConversationRepository()
    personalization_repo = FakePersonalizationRepository(_context())

    async def request():
        response = await routes_chat.chat_stream(
            ChatRequest(message="What deadlines are coming up?"),
            current_user=_student_user(),
            conversation_repository=conversation_repo,
            personalization_repository=personalization_repo,
        )
        chunks = []
        async for chunk in response.body_iterator:
            chunks.append(chunk.decode() if isinstance(chunk, bytes) else chunk)
        return "".join(chunks)

    body = _run(request())

    assert "event: done" in body
    assert personalization_repo.calls == [STUDENT_USER_ID]
    assert captured["personalization"] is not None
    assert "CSC202" in captured["personalization"]
    assert captured["message"] == "What deadlines are coming up?"
    user_messages = [row for row in conversation_repo.appended if row["role"] == "user"]
    assert user_messages[0]["content"] == "What deadlines are coming up?"


def test_anonymous_chat_attaches_no_personalization(monkeypatch):
    captured: dict[str, Any] = {}
    monkeypatch.setattr(routes_chat, "_resolve_chat", _capturing_resolver(captured))
    personalization_repo = FakePersonalizationRepository(_context())

    response = _run(
        routes_chat.chat(
            ChatRequest(message="When is add/drop?"),
            personalization_repository=personalization_repo,
        )
    )

    assert response.answer == "Personalized answer."
    # No authenticated user → context lookup is never attempted.
    assert personalization_repo.calls == []
    assert captured["personalization"] is None


def test_admin_chat_does_not_use_student_personalization(monkeypatch):
    captured: dict[str, Any] = {}
    monkeypatch.setattr(routes_chat, "_resolve_chat", _capturing_resolver(captured))
    conversation_repo = FakeConversationRepository()
    personalization_repo = FakePersonalizationRepository(_context())

    _run(
        routes_chat.chat(
            ChatRequest(message="Show me the dashboard."),
            current_user=_admin_user(),
            conversation_repository=conversation_repo,
            personalization_repository=personalization_repo,
        )
    )

    # A non-student role never triggers a student-context lookup.
    assert personalization_repo.calls == []
    assert captured["personalization"] is None


def test_client_supplied_personalization_is_ignored_for_non_students(monkeypatch):
    captured: dict[str, Any] = {}
    monkeypatch.setattr(routes_chat, "_resolve_chat", _capturing_resolver(captured))
    personalization_repo = FakePersonalizationRepository(_context())

    request = ChatRequest(message="Hello")
    # Simulate a client trying to smuggle a fabricated context in.
    request.backend_personalization_context = "FAKE INJECTED CONTEXT"

    _run(
        routes_chat.chat(
            request,
            personalization_repository=personalization_repo,
        )
    )

    # The route clears any client-supplied value before resolving.
    assert captured["personalization"] is None


def test_student_with_personalization_disabled_gets_no_context(monkeypatch):
    captured: dict[str, Any] = {}
    monkeypatch.setattr(routes_chat, "_resolve_chat", _capturing_resolver(captured))
    conversation_repo = FakeConversationRepository()
    personalization_repo = FakePersonalizationRepository(_context(ai_enabled=False))

    _run(
        routes_chat.chat(
            ChatRequest(message="When is my next class?"),
            current_user=_student_user(),
            conversation_repository=conversation_repo,
            personalization_repository=personalization_repo,
        )
    )

    assert personalization_repo.calls == [STUDENT_USER_ID]
    assert captured["personalization"] is None


# --- Agent output-guard acceptance (Phase 14A hotfix) ----------------------------------------
# These exercise the REAL deterministic output guard via VinUniAgentService with a fake agent, so
# no live LLM is involved.


class _FakeAgent:
    def __init__(self, answer: str) -> None:
        self.answer = answer

    async def ainvoke(self, payload, config):
        # No ToolMessage in the trace → the answer has no RAG citations, mirroring a personal
        # app-data answer that is grounded only in the backend personalization context.
        return {"messages": [SimpleNamespace(content=self.answer)]}


def _stub_input_guard(monkeypatch):
    """Force the INPUT guardrail to a confident allow so the agent never consults the remote
    scope-router / safety APIs. Keeps the test offline while leaving the OUTPUT guard real."""
    from vinchatbot.app.agents.guardrails import GuardrailDecision

    async def _allow(*_args, **_kwargs):
        return GuardrailDecision(action="allow", reason="test stub")

    monkeypatch.setattr(agent_mod, "resolve_guardrail_decision", _allow)


def _agent_service(answer: str, **settings_overrides: Any):
    # Disable output moderation AND follow-up suggestions so the test stays fully offline (no
    # safety-model / follow-up-model call). Individual tests can re-enable follow-ups via overrides.
    settings = get_settings().model_copy(
        update={
            "enable_output_moderation": False,
            "enable_followup_suggestions": False,
            **settings_overrides,
        }
    )
    return agent_mod.VinUniAgentService(
        settings=settings, retriever=SimpleNamespace(), agent=_FakeAgent(answer)
    )


def test_agent_serves_personal_app_data_answer_from_trusted_context(monkeypatch):
    _stub_input_guard(monkeypatch)
    answer = (
        "Bạn có 1 thông báo quan trọng: Required CECS lab safety training "
        "(mức độ urgent, đến 2026-10-04)."
    )
    service = _agent_service(answer)
    request = ChatRequest(
        message="Có thông báo nào quan trọng không?", conversation_id="p14a-trusted"
    )
    # Server-built context (a client could not set this — the route clears it first).
    request.backend_personalization_context = (
        "Active notifications:\n- [urgent] Required CECS lab safety training (due 2026-10-04)"
    )

    response = _run(service.chat(request))

    # The uncited personal app-data answer is served, NOT degraded to the official-source fallback.
    assert response.answer == answer
    assert any(
        trace.get("type") == "output_guard" and trace.get("action") == "allow"
        for trace in response.tool_trace
    )


def test_agent_degrades_official_policy_answer_without_citations(monkeypatch):
    _stub_input_guard(monkeypatch)
    answer = "Quy định rút môn cho phép sinh viên rút môn trong 2 tuần đầu của học kỳ."
    service = _agent_service(answer)
    # No backend context → trusted_app_data is False → the RAG citation requirement still applies.
    request = ChatRequest(message="Quy định rút môn là gì?", conversation_id="p14a-policy")

    response = _run(service.chat(request))

    assert response.answer != answer  # degraded to the unknown-answer fallback
    assert response.needs_human_review is True


def test_agent_hybrid_question_still_requires_citations_for_policy(monkeypatch):
    _stub_input_guard(monkeypatch)
    answer = "Bạn đang học CSC202. Quy định rút môn cho phép rút trong 2 tuần đầu."
    service = _agent_service(answer)
    request = ChatRequest(
        message="Tôi có thể rút môn CSC250 không?", conversation_id="p14a-hybrid"
    )
    request.backend_personalization_context = "Current courses:\n- CSC202 Data Structures"

    response = _run(service.chat(request))

    # Hybrid scope does NOT grant the trusted bypass, so an uncited policy claim still degrades.
    assert response.answer != answer


# --- Checkpointer isolation (cross-student memory bleed) --------------------------------------
# The LangGraph checkpointer replays a thread's full history into every turn, carrying the prior
# turn's personalization context + personal-tool results. The thread_id MUST be namespaced by the
# verified user so two signed-in students who share a client-supplied conversation_id can never
# share agent memory (which would make the bot answer student B with student A's replayed identity).


class _ConfigCapturingAgent:
    def __init__(self) -> None:
        self.configs: list[dict[str, Any]] = []

    async def ainvoke(self, payload, config):
        self.configs.append(config)
        return {"messages": [SimpleNamespace(content="ok")]}


def _capturing_service(monkeypatch) -> tuple[Any, _ConfigCapturingAgent]:
    _stub_input_guard(monkeypatch)
    settings = get_settings().model_copy(update={"enable_output_moderation": False})
    agent = _ConfigCapturingAgent()
    service = agent_mod.VinUniAgentService(
        settings=settings, retriever=SimpleNamespace(), agent=agent
    )
    return service, agent


def test_checkpointer_thread_is_namespaced_by_verified_user(monkeypatch):
    service, agent = _capturing_service(monkeypatch)
    token = set_student_identity(student_profile_id=PROFILE_ID, user_id=STUDENT_USER_ID)
    try:
        _run(service.chat(ChatRequest(message="GPA của tôi là bao nhiêu?", conversation_id="shared")))
    finally:
        reset_student_identity(token)
    assert agent.configs[0]["configurable"]["thread_id"] == f"u:{STUDENT_USER_ID}:shared"


def test_checkpointer_thread_unnamespaced_without_identity(monkeypatch):
    service, agent = _capturing_service(monkeypatch)
    _run(service.chat(ChatRequest(message="VinUni có ngành nào?", conversation_id="shared")))
    assert agent.configs[0]["configurable"]["thread_id"] == "shared"


def test_two_students_sharing_conversation_id_get_distinct_threads(monkeypatch):
    service, agent = _capturing_service(monkeypatch)
    other_user_id = uuid.UUID("ffffffff-ffff-ffff-ffff-ffffffffffff")
    for uid in (STUDENT_USER_ID, other_user_id):
        token = set_student_identity(student_profile_id=PROFILE_ID, user_id=uid)
        try:
            _run(service.chat(ChatRequest(message="Mã số sinh viên của tôi?", conversation_id="dup")))
        finally:
            reset_student_identity(token)
    threads = [c["configurable"]["thread_id"] for c in agent.configs]
    assert threads[0] != threads[1]  # same conversation_id, different verified users → no shared memory


# --- Follow-up suggestions wiring ------------------------------------------------------------
# A successful answer attaches backend-generated follow-ups (a small/fast model, stubbed here). The
# flag gates it off entirely; failures are swallowed so the turn is never affected.


# A trusted personal-app-data turn (uncited answer is served, not degraded) so the SUCCESS path runs.
_FU_ANSWER = "GPA của bạn hiện là 3.4."
_FU_CONTEXT = "Academic standing: good standing; GPA 3.4; credits 60/120."


def _follow_up_request(conv: str) -> ChatRequest:
    request = ChatRequest(message="GPA của tôi là bao nhiêu?", conversation_id=conv)
    request.backend_personalization_context = _FU_CONTEXT
    return request


def test_successful_answer_attaches_backend_follow_ups(monkeypatch):
    _stub_input_guard(monkeypatch)

    async def _fake(question, answer, settings):
        return ["Làm sao để cải thiện GPA?", "Tôi cần GPA bao nhiêu để tốt nghiệp loại Giỏi?"]

    monkeypatch.setattr(agent_mod, "suggest_follow_ups", _fake)
    service = _agent_service(_FU_ANSWER, enable_followup_suggestions=True)

    response = _run(service.chat(_follow_up_request("fu-1")))
    assert response.answer == _FU_ANSWER  # not degraded
    assert response.suggested_follow_ups == [
        "Làm sao để cải thiện GPA?",
        "Tôi cần GPA bao nhiêu để tốt nghiệp loại Giỏi?",
    ]


def test_follow_ups_disabled_by_flag(monkeypatch):
    _stub_input_guard(monkeypatch)

    async def _boom(*_a, **_k):  # must not be called when the flag is off
        raise AssertionError("suggest_follow_ups called while disabled")

    monkeypatch.setattr(agent_mod, "suggest_follow_ups", _boom)
    service = _agent_service(_FU_ANSWER, enable_followup_suggestions=False)

    response = _run(service.chat(_follow_up_request("fu-2")))
    assert response.answer == _FU_ANSWER
    assert response.suggested_follow_ups == []


def test_follow_up_failure_does_not_break_turn(monkeypatch):
    _stub_input_guard(monkeypatch)

    async def _raise(*_a, **_k):
        raise RuntimeError("follow-up model down")

    monkeypatch.setattr(agent_mod, "suggest_follow_ups", _raise)
    service = _agent_service(_FU_ANSWER, enable_followup_suggestions=True)

    response = _run(service.chat(_follow_up_request("fu-3")))  # must not raise
    assert response.answer == _FU_ANSWER
    assert response.suggested_follow_ups == []
