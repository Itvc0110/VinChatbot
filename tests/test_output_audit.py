from __future__ import annotations

import asyncio
from types import SimpleNamespace

import vinchatbot.app.agents.vinuni_agent as agent_mod
from vinchatbot.app.agents.guardrails import OutputAuditDecision
from vinchatbot.app.agents.output_audit import OutputAuditVerdict, audit_output, parse_verdict
from vinchatbot.app.core.config import get_settings
from vinchatbot.app.schemas.chat import ChatRequest

# --- parse_verdict (tolerant, defaults to grounded=True) ---------------------------------------

def test_parse_verdict_grounded_true_false():
    assert parse_verdict('{"grounded": true, "unsupported_claims": [], "reason": "ok"}').grounded is True
    v = parse_verdict('{"grounded": false, "unsupported_claims": ["wrong year"], "reason": "2030 not in evidence"}')
    assert v.grounded is False
    assert "2030 not in evidence" in v.reason


def test_parse_verdict_defaults_true_on_garbage():
    # A malformed/odd response must NOT degrade a good answer.
    assert parse_verdict("the model rambled with no json").grounded is True
    assert parse_verdict("").grounded is True


def test_parse_verdict_bareword_unsupported_is_false():
    assert parse_verdict("verdict: unsupported — the figure is fabricated").grounded is False


# --- audit_output (fail-OPEN everywhere except a confident grounded:false) ----------------------

class _MockModel:
    def __init__(self, content: str):
        self.content = content

    async def ainvoke(self, messages):
        return SimpleNamespace(content=self.content)


def _settings(key: str = "test-key"):
    return SimpleNamespace(
        openrouter_api_key=key, guard_model="qwen/qwen-2.5-7b-instruct", output_audit_model=""
    )


def test_audit_output_flags_ungrounded():
    v = asyncio.run(
        audit_output(
            "The Fall 2030 grades are released on 21 September 2030.",
            ["Fall 2026 grade release: 21 September."],
            "When are Fall 2030 grades released?",
            _settings(),
            model=_MockModel('{"grounded": false, "unsupported_claims": ["2030"], "reason": "year fabricated"}'),
        )
    )
    assert v.grounded is False


def test_audit_output_passes_grounded():
    v = asyncio.run(
        audit_output(
            "The library lends 3 items for 2 weeks.",
            ["Undergraduates may borrow 3 items for 2 weeks."],
            "How many items can I borrow?",
            _settings(),
            model=_MockModel('{"grounded": true, "unsupported_claims": [], "reason": "matches"}'),
        )
    )
    assert v.grounded is True


def test_audit_output_fail_open_without_key_or_evidence():
    # No key, no evidence → never degrade (grounded=True), and the model is never consulted.
    assert asyncio.run(audit_output("x", ["e"], "q", _settings(key=""))).grounded is True
    assert asyncio.run(audit_output("x", [], "q", _settings())).grounded is True


# --- chat() seam: gated, scoped to point-lookups, degrades only on grounded:false ---------------

class _FakeAgent:
    def __init__(self, answer: str):
        self.answer = answer
        self.calls = 0

    async def ainvoke(self, payload, config):
        self.calls += 1
        return {"messages": [SimpleNamespace(content=self.answer)]}


def _audit_service(monkeypatch, *, grounded: bool, point_lookup: bool = True):
    # Force Phase A to ALLOW so control reaches the Phase B seam, mark the turn high-stakes, and stub
    # the LLM auditor to a fixed verdict.
    monkeypatch.setattr(agent_mod, "resolve_output_decision", lambda *a, **k: OutputAuditDecision("allow", "t"))
    # Scope gate is is_point_lookup(message, intent) computed in chat() (the contextvar doesn't survive
    # the LangGraph node boundary back to chat()).
    monkeypatch.setattr(agent_mod, "is_point_lookup", lambda *a, **k: point_lookup)

    async def _stub_audit(*a, **k):
        return OutputAuditVerdict(grounded, [], "stub")

    monkeypatch.setattr(agent_mod, "audit_output", _stub_audit)
    settings = get_settings().model_copy(update={"enable_output_audit": True})
    agent = _FakeAgent("The tuition is 999,000,000 VND per year.")
    service = agent_mod.VinUniAgentService(settings=settings, retriever=SimpleNamespace(), agent=agent)
    return service, agent


def test_output_audit_degrades_confidently_wrong(monkeypatch):
    service, agent = _audit_service(monkeypatch, grounded=False)
    resp = asyncio.run(service.chat(ChatRequest(message="What is the nursing tuition per year?", conversation_id="audit-1")))
    assert agent.calls == 1
    assert resp.needs_human_review is True
    assert "999,000,000" not in resp.answer  # the wrong figure was NOT served
    assert any(t.get("type") == "output_audit" and t.get("grounded") is False for t in resp.tool_trace)


def test_output_audit_serves_grounded_answer(monkeypatch):
    service, agent = _audit_service(monkeypatch, grounded=True)
    resp = asyncio.run(service.chat(ChatRequest(message="What is the nursing tuition per year?", conversation_id="audit-2")))
    assert "999,000,000" in resp.answer  # grounded → served unchanged
    assert any(t.get("type") == "output_audit" and t.get("grounded") is True for t in resp.tool_trace)


def test_output_audit_skipped_when_not_point_lookup(monkeypatch):
    # Scope gate: a non-point-lookup turn must NOT invoke the auditor (so a grounded:false stub can't
    # degrade it) — the answer is served.
    service, agent = _audit_service(monkeypatch, grounded=False, point_lookup=False)
    resp = asyncio.run(service.chat(ChatRequest(message="What is the nursing tuition per year?", conversation_id="audit-3")))
    assert "999,000,000" in resp.answer


def test_output_audit_real_scope_gate_opens_on_point_lookup(monkeypatch):
    # Regression guard for the wiring bug: the scope signal must be is_point_lookup(message, intent)
    # computed IN chat(), because mark_point_lookup's contextvar set inside the LangGraph tool node does
    # NOT propagate back to the parent context. A real tuition point-lookup must open the gate WITHOUT
    # monkeypatching the signal — earlier the auditor fired on 0 cases because get_point_lookup() was
    # always False here.
    monkeypatch.setattr(agent_mod, "resolve_output_decision", lambda *a, **k: OutputAuditDecision("allow", "t"))

    async def _stub(*a, **k):
        return OutputAuditVerdict(False, [], "stub")

    monkeypatch.setattr(agent_mod, "audit_output", _stub)
    settings = get_settings().model_copy(update={"enable_output_audit": True})
    agent = _FakeAgent("The tuition is 999,000,000 VND per year.")
    service = agent_mod.VinUniAgentService(settings=settings, retriever=SimpleNamespace(), agent=agent)
    resp = asyncio.run(
        service.chat(ChatRequest(message="What is the nursing tuition per year?", conversation_id="audit-real"))
    )
    assert "999,000,000" not in resp.answer  # real is_point_lookup gate opened → auditor degraded it
