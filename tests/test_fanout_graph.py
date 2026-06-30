"""Phase 1.33 fan-out: dispatch planner + parallel specialists + synthesis merge.

Offline (no network/key): the dispatch decision is injected via `dispatch_planner` and the synthesis
model via `model` — the exact analog of the existing `supervisor_router` injection in test_agent_graph.py.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.checkpoint.memory import InMemorySaver

from vinchatbot.app.agents.graph import (
    FANOUT_ROUTE,
    _history_context,
    _last_ai_text,
    _msg_content,
    _tool_messages,
    build_agent_graph,
)
from vinchatbot.app.agents.supervisor import (
    INTENTS,
    _looks_multi,
    _parse_plan,
    _single_plan,
    plan_dispatch,
)
from vinchatbot.app.core.observability import get_user_message, reset_user_message, set_user_message


def _fake_specialist(name: str, *, answer: str | None = None, tool_payload: str | None = None,
                     raises: bool = False, record: dict | None = None):
    """A specialist stub that records the payload it received, optionally raises, and emits a
    ToolMessage (evidence) + an AIMessage (answer) like a real ReAct specialist's final state."""
    class _Agent:
        async def ainvoke(self, payload, config=None):
            if record is not None:
                record[name] = payload["messages"]
            if raises:
                raise RuntimeError(f"{name} boom")
            tool = ToolMessage(content=tool_payload or f"[evidence {name}]", tool_call_id=f"{name}-call")
            reply = AIMessage(content=f"answer from {name}" if answer is None else answer)
            return {"messages": [*payload["messages"], tool, reply]}

    return _Agent()


class _FakeModel:
    """Synthesis stand-in: echoes the user prompt (which carries every subtask's answer) so tests can
    assert the merge SAW each part."""
    async def ainvoke(self, messages, config=None):
        last = messages[-1]
        content = last["content"] if isinstance(last, dict) else getattr(last, "content", "")
        return AIMessage(content="MERGED:: " + content)


def _build_fanout_graph(plan: list[dict], *, specialists=None, model=None):
    async def planner(_text: str) -> list[dict]:
        return plan

    specialists = specialists or {intent: _fake_specialist(intent) for intent in INTENTS}
    return build_agent_graph(
        retriever=None,
        specialists=specialists,
        dispatch_planner=planner,
        model=model or _FakeModel(),
        checkpointer=InMemorySaver(),
    )


def _invoke(graph, text: str, thread: str) -> dict:
    return asyncio.run(
        graph.ainvoke(
            {"messages": [{"role": "user", "content": text}]},
            config={"configurable": {"thread_id": thread}},
        )
    )


# --- graph: fan-out behaviors ---------------------------------------------------------------------

def test_fanout_merges_subtasks_and_unions_citations():
    record: dict = {}
    specialists = {
        "financial": _fake_specialist("financial", answer="tuition is 815,850,000 VND",
                                      tool_payload="FIN_EVIDENCE", record=record),
        "calendar": _fake_specialist("calendar", answer="Fall begins September 21, 2026",
                                     tool_payload="CAL_EVIDENCE", record=record),
        "policy": _fake_specialist("policy"),
        "services": _fake_specialist("services"),
    }
    plan = [{"query": "MD tuition?", "intent": "financial"},
            {"query": "Fall start?", "intent": "calendar"}]
    out = _invoke(_build_fanout_graph(plan, specialists=specialists), "MD tuition and Fall start?", "f1")

    assert out["intent"] == FANOUT_ROUTE
    final = out["messages"][-1]
    assert getattr(final, "type", None) == "ai"  # the synthesis reply is LAST
    # synthesis saw BOTH subtasks' grounded answers
    assert "815,850,000" in final.content and "September 21, 2026" in final.content
    # both subtasks' ToolMessages are present so the service layer unions citations with no change
    tool_contents = [m.content for m in out["messages"] if getattr(m, "type", None) == "tool"]
    assert "FIN_EVIDENCE" in tool_contents and "CAL_EVIDENCE" in tool_contents


def test_fanout_feeds_only_subtask_to_each_specialist():
    record: dict = {}
    specialists = {intent: _fake_specialist(intent, record=record) for intent in INTENTS}
    plan = [{"query": "SUBTASK_FIN", "intent": "financial"},
            {"query": "SUBTASK_CAL", "intent": "calendar"}]
    _invoke(_build_fanout_graph(plan, specialists=specialists), "WHOLE COMPOUND QUESTION", "f2")

    # each specialist got a FRESH single-message context = ONLY its subtask, not the whole conversation
    assert len(record["financial"]) == 1 and record["financial"][0]["content"] == "SUBTASK_FIN"
    assert len(record["calendar"]) == 1 and record["calendar"][0]["content"] == "SUBTASK_CAL"
    assert "WHOLE COMPOUND QUESTION" not in record["financial"][0]["content"]


def test_fanout_isolates_a_failed_subtask():
    specialists = {
        "financial": _fake_specialist("financial", answer="tuition is 815,850,000", tool_payload="FIN"),
        "calendar": _fake_specialist("calendar", raises=True),  # blows up; must not kill the turn
        "policy": _fake_specialist("policy"),
        "services": _fake_specialist("services"),
    }
    plan = [{"query": "fin?", "intent": "financial"}, {"query": "cal?", "intent": "calendar"}]
    out = _invoke(_build_fanout_graph(plan, specialists=specialists), "q", "f3")

    final = out["messages"][-1].content
    assert "815,850,000" in final  # the healthy subtask still landed
    assert "không truy xuất được" in final  # the failed one is named as a gap, not silently dropped


def test_fanout_reroutes_empty_subtask_to_services():
    record: dict = {}
    specialists = {
        "financial": _fake_specialist("financial", answer="", record=record),  # empty → reroute
        "services": _fake_specialist("services", answer="services recovered: 42", record=record),
        "calendar": _fake_specialist("calendar", answer="cal ok"),
        "policy": _fake_specialist("policy"),
    }
    plan = [{"query": "ambiguous q", "intent": "financial"}, {"query": "cal q", "intent": "calendar"}]
    out = _invoke(_build_fanout_graph(plan, specialists=specialists), "q", "f4")

    assert "services recovered: 42" in out["messages"][-1].content
    # the SAME subtask query was re-dispatched to services
    assert record["services"][0]["content"] == "ambiguous q"


def test_single_assignment_plan_uses_single_specialist_path():
    record: dict = {}
    specialists = {intent: _fake_specialist(intent, record=record) for intent in INTENTS}
    # planner query intentionally DIFFERS from the user text to prove the single path uses the real state
    plan = [{"query": "reworded", "intent": "policy"}]
    out = _invoke(_build_fanout_graph(plan, specialists=specialists), "WHOLE STATE Q", "f5")

    assert out["intent"] == "policy"
    assert "answer from policy" in out["messages"][-1].content
    assert out.get("plan") in (None, [])  # single path never sets a fan-out plan
    # full conversation state reaches the specialist (LangGraph normalizes the dict to a message object),
    # NOT the planner's reworded subtask
    assert _msg_content(record["policy"][0]) == "WHOLE STATE Q"


def test_single_assignment_defers_to_calibrated_router():
    # Phase 1.33: when BOTH a planner and a router are present and the plan is SINGLE, the calibrated router
    # decides the intent (byte-identical single-domain routing) — the planner's single-intent is NOT used.
    async def planner(_text: str) -> list[dict]:
        return [{"query": "whole q", "intent": "financial"}]  # planner says financial

    async def router(_text: str) -> str:
        return "policy"  # calibrated router says policy → must win

    specialists = {intent: _fake_specialist(intent) for intent in INTENTS}
    graph = build_agent_graph(
        retriever=None, specialists=specialists, dispatch_planner=planner,
        supervisor_router=router, model=_FakeModel(), checkpointer=InMemorySaver(),
    )
    out = _invoke(graph, "q", "f7")
    assert out["intent"] == "policy"  # router wins on single, not the planner's "financial"


def test_flag_off_router_injected_keeps_single_path():
    async def router(_text: str) -> str:
        return "calendar"

    specialists = {intent: _fake_specialist(intent) for intent in INTENTS}
    graph = build_agent_graph(
        retriever=None, specialists=specialists, supervisor_router=router, checkpointer=InMemorySaver()
    )
    out = _invoke(graph, "q", "f6")
    assert out["intent"] == "calendar"
    assert out.get("plan") in (None, [])  # fan-out never engaged


# --- L2 reactive completeness loop ----------------------------------------------------------------

def _counting_specialist(name: str, answer: str):
    class _Agent:
        def __init__(self):
            self.calls = 0

        async def ainvoke(self, payload, config=None):
            self.calls += 1
            tool = ToolMessage(content=f"ev-{name}", tool_call_id=f"{name}-{self.calls}")
            return {"messages": [*payload["messages"], tool, AIMessage(content=answer)]}

    return _Agent()


def _punt_then_recover_specialist(name: str, recovered: str):
    class _Agent:
        def __init__(self):
            self.calls = 0

        async def ainvoke(self, payload, config=None):
            self.calls += 1
            is_retry = "[Retry note" in _msg_content(payload["messages"][-1])
            reply = recovered if is_retry else "No official information available."
            tool = ToolMessage(content=f"ev-{name}", tool_call_id=f"{name}-{self.calls}")
            return {"messages": [*payload["messages"], tool, AIMessage(content=reply)]}

    return _Agent()


def _always_punt_specialist(name: str):
    class _Agent:
        def __init__(self):
            self.calls = 0

        async def ainvoke(self, payload, config=None):
            self.calls += 1
            tool = ToolMessage(content=f"ev-{name}", tool_call_id=f"{name}-{self.calls}")
            return {"messages": [*payload["messages"], tool, AIMessage(content="No information available.")]}

    return _Agent()


def test_l2_reruns_punted_subtask_and_recovers():
    fin = _punt_then_recover_specialist("financial", "tuition is 815,850,000 VND")
    specialists = {
        "financial": fin,
        "calendar": _fake_specialist("calendar", answer="Fall begins September 21, 2026"),
        "policy": _fake_specialist("policy"),
        "services": _fake_specialist("services"),
    }
    plan = [{"query": "MD tuition?", "intent": "financial"}, {"query": "Fall start?", "intent": "calendar"}]
    out = _invoke(_build_fanout_graph(plan, specialists=specialists), "q", "l1")
    assert fin.calls == 2  # original punt + one critique-fed retry
    assert "815,850,000" in out["messages"][-1].content  # recovered value made it into the merge


def test_l2_does_not_rerun_satisfactory_subtask():
    fin = _counting_specialist("financial", "tuition is 815,850,000 VND")
    cal = _counting_specialist("calendar", "Fall begins September 21, 2026")
    specialists = {
        "financial": fin, "calendar": cal,
        "policy": _fake_specialist("policy"), "services": _fake_specialist("services"),
    }
    plan = [{"query": "a", "intent": "financial"}, {"query": "b", "intent": "calendar"}]
    _invoke(_build_fanout_graph(plan, specialists=specialists), "q", "l2")
    assert fin.calls == 1 and cal.calls == 1  # neither punted → no L2 retry (zero extra calls)


def test_l2_keeps_original_when_retry_also_punts():
    fin = _always_punt_specialist("financial")  # truly out-of-scope: punts on retry too
    specialists = {
        "financial": fin,
        "calendar": _fake_specialist("calendar", answer="Fall begins September 21, 2026"),
        "policy": _fake_specialist("policy"), "services": _fake_specialist("services"),
    }
    plan = [{"query": "oos?", "intent": "financial"}, {"query": "b", "intent": "calendar"}]
    out = _invoke(_build_fanout_graph(plan, specialists=specialists), "q", "l3")
    assert fin.calls == 2  # tried exactly one retry, did not fabricate
    assert "September 21, 2026" in out["messages"][-1].content  # the good subtask still landed


def test_fanout_points_contextvar_at_subtask_not_compound():
    # Phase 1.33 root-cause guard: the turn pins get_user_message() to the WHOLE compound; each fan-out
    # subtask must run with the contextvar set to ITS OWN subtask (else the specialist's structured-lookup /
    # list-mode / cross-lingual logic keys off the wrong text and punts). asyncio.gather isolates contexts.
    seen: dict = {}

    def _recording_specialist(name: str):
        class _Agent:
            async def ainvoke(self, payload, config=None):
                seen[name] = get_user_message()
                tool = ToolMessage(content=f"ev-{name}", tool_call_id=f"{name}-1")
                return {"messages": [*payload["messages"], tool, AIMessage(content=f"answer from {name}")]}

        return _Agent()

    specialists = {intent: _recording_specialist(intent) for intent in INTENTS}
    plan = [{"query": "SUBTASK_FIN", "intent": "financial"}, {"query": "SUBTASK_CAL", "intent": "calendar"}]
    set_user_message("WHOLE COMPOUND QUESTION")
    try:
        _invoke(_build_fanout_graph(plan, specialists=specialists), "WHOLE COMPOUND QUESTION", "ctx1")
    finally:
        reset_user_message()
    assert seen["financial"] == "SUBTASK_FIN"  # each subtask saw ITS query, not the compound
    assert seen["calendar"] == "SUBTASK_CAL"


# --- supervisor: pure planner helpers -------------------------------------------------------------

def test_parse_plan_valid_fenced_and_invalid():
    assert _parse_plan('[{"query":"a","intent":"financial"},{"query":"b","intent":"calendar"}]') == [
        {"query": "a", "intent": "financial"}, {"query": "b", "intent": "calendar"}]
    assert _parse_plan('```json\n[{"query":"x","intent":"policy"}]\n```') == [
        {"query": "x", "intent": "policy"}]
    assert _parse_plan('[{"query":"x","intent":"sports"}]') is None   # bad intent dropped → empty → None
    assert _parse_plan('[{"intent":"financial"}]') is None            # missing query
    assert _parse_plan("not json at all") is None
    assert _parse_plan("[]") is None


def test_single_plan_and_looks_multi():
    sp = _single_plan("How much is tuition?")
    assert len(sp) == 1 and sp[0]["query"] == "How much is tuition?" and sp[0]["intent"] in INTENTS
    assert _looks_multi("tuition and deadline?")
    assert _looks_multi("học phí và lịch học?")
    assert _looks_multi("Q1? Q2?")
    assert not _looks_multi("How much is tuition for the fall semester?")


def test_plan_dispatch_tier0_single_domain_is_offline():
    # single-domain, non-compound → Tier-0 returns SINGLE before any LLM/key is touched
    plan = asyncio.run(plan_dispatch("How much is tuition?"))
    assert len(plan) == 1 and plan[0]["intent"] == "financial"


def _fake_settings():
    return SimpleNamespace(openrouter_api_key="x", fan_out_max_subtasks=3,
                           planner_model="", openrouter_chat_model="test-model")


def test_plan_dispatch_llm_branch_decomposes():
    class _M:
        async def ainvoke(self, messages, config=None):
            return AIMessage(content='[{"query":"tuition?","intent":"financial"},'
                                     '{"query":"deadline?","intent":"calendar"}]')

    plan = asyncio.run(plan_dispatch("What is tuition and the drop deadline?",
                                     settings=_fake_settings(), model=_M()))
    assert [p["intent"] for p in plan] == ["financial", "calendar"]


def test_plan_dispatch_collapses_same_intent_overfire():
    # Phase 1.33: a multi-assignment plan whose parts ALL route to the same specialist is an over-fire →
    # collapse to a SINGLE whole-question assignment (the byte-identical single path). Guards the 4 measured
    # full-199 same-specialist regressions (e.g. "Fall AND Spring deadline" both calendar).
    class _M:
        async def ainvoke(self, messages, config=None):
            return AIMessage(content='[{"query":"who forms it?","intent":"policy"},'
                                     '{"query":"who approves it?","intent":"policy"}]')

    plan = asyncio.run(plan_dispatch("Who forms it and who approves it?", settings=_fake_settings(), model=_M()))
    assert len(plan) == 1 and plan[0]["intent"] == "policy"
    assert plan[0]["query"] == "Who forms it and who approves it?"  # whole question, not a split subtask


def test_plan_dispatch_keeps_distinct_intent_decompose():
    class _M:
        async def ainvoke(self, messages, config=None):
            return AIMessage(content='[{"query":"tuition?","intent":"financial"},'
                                     '{"query":"start date?","intent":"calendar"}]')

    plan = asyncio.run(plan_dispatch("tuition and start date?", settings=_fake_settings(), model=_M()))
    assert len(plan) == 2  # genuine cross-domain (distinct intents) is NOT collapsed


def test_plan_dispatch_caps_subtasks():
    class _M:
        async def ainvoke(self, messages, config=None):
            return AIMessage(content='[{"query":"a","intent":"financial"},{"query":"b","intent":"calendar"},'
                                     '{"query":"c","intent":"policy"},{"query":"d","intent":"services"}]')

    plan = asyncio.run(plan_dispatch("a and b and c and d?", settings=_fake_settings(), model=_M()))
    assert len(plan) == 3  # capped at fan_out_max_subtasks


def test_plan_dispatch_failsafe_on_garbage():
    class _M:
        async def ainvoke(self, messages, config=None):
            return AIMessage(content="I cannot help with that")

    plan = asyncio.run(plan_dispatch("tuition and deadline?", settings=_fake_settings(), model=_M()))
    assert len(plan) == 1  # unparseable → fail safe to a single assignment


# --- helpers --------------------------------------------------------------------------------------

def test_history_context_formats_prior_turns_and_excludes_current():
    msgs = [HumanMessage(content="first q"), AIMessage(content="first a"), HumanMessage(content="current q")]
    ctx = _history_context(msgs)
    assert "first q" in ctx and "first a" in ctx
    assert "current q" not in ctx  # the latest (current) message is excluded


def test_tool_messages_and_last_ai_text():
    msgs = [HumanMessage(content="q"), ToolMessage(content="ev", tool_call_id="c1"),
            AIMessage(content="the answer")]
    assert [m.content for m in _tool_messages(msgs)] == ["ev"]
    assert _last_ai_text(msgs) == "the answer"
    assert _last_ai_text([HumanMessage(content="q")]) == ""  # no AI text
