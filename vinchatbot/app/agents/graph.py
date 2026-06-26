"""LangGraph multi-agent graph.

Flow (ENABLE_FAN_OUT off, default): START -> supervisor (sets intent) -> <specialist> -> END.
  Byte-identical to pre-1.33 single-specialist routing.
Flow (ENABLE_FAN_OUT on, multi-assignment plan): START -> supervisor (sets a dispatch plan) -> fanout
  (run the matched specialists in PARALLEL, then a synthesis node merges them) -> END. A single-assignment
  plan still takes the single-specialist path, so the common case is unchanged.

Output guarding (sensitive/citation/faithfulness/intent) is applied at the service layer (VinUniAgentService)
on the graph's message output; the contract `ainvoke({"messages":[...]}) -> {"messages":[...]}` is unchanged.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

from langchain_core.messages import AIMessage
from langgraph.graph import END, START, MessagesState, StateGraph

from vinchatbot.app.agents.prompts import SYNTHESIS_SYSTEM
from vinchatbot.app.agents.specialists import build_specialists
from vinchatbot.app.agents.supervisor import INTENTS, plan_dispatch, route_intent
from vinchatbot.app.core.config import Settings, get_settings
from vinchatbot.app.core.observability import record_llm_usage, set_user_message
from vinchatbot.app.llm.openrouter_chat import build_chat_model
from vinchatbot.app.rag.retriever import Retriever

# Sentinel "intent" value routing the supervisor to the fan-out node (Phase 1.33).
FANOUT_ROUTE = "__fanout__"


class VinUniState(MessagesState):
    intent: str
    plan: list  # fan-out dispatch plan [{query,intent}] (only set when fanning out; unused on the single path)


def _msg_role(message: Any) -> str | None:
    if isinstance(message, dict):
        return message.get("role") or message.get("type")
    return getattr(message, "type", None)


def _msg_content(message: Any) -> str:
    content = message.get("content", "") if isinstance(message, dict) else getattr(message, "content", "")
    return content if isinstance(content, str) else str(content)


def _last_user_text(messages: list[Any]) -> str:
    for message in reversed(messages):
        if _msg_role(message) in ("human", "user"):
            return _msg_content(message)
    if messages:
        return _msg_content(messages[-1])
    return ""


def _last_ai_text(messages: list[Any]) -> str:
    for message in reversed(messages):
        if _msg_role(message) == "ai" and _msg_content(message).strip():
            return _msg_content(message)
    return ""


def _tool_messages(messages: list[Any]) -> list[Any]:
    """The ToolMessages (retrieval payloads) from a specialist's run — the service layer extracts citations +
    evidence from these, so collecting them across subtasks unions the evidence with no service-layer change."""
    return [m for m in messages if _msg_role(m) in ("tool", "tool_result")]


# Phase 1.33 L2: a subtask "punted" — returned no usable specific value although the fact likely exists. These
# markers are deliberately STRONG/explicit so a partial-but-useful answer is not needlessly re-run.
_PUNT_MARKERS = (
    "no official information", "no information available", "not available", "is not available",
    "isn't available", "could not find", "couldn't find", "unable to find", "no specific information",
    "không tìm thấy", "chưa tìm thấy", "không có thông tin", "không tìm được", "chưa có thông tin",
)


def _is_punt(text: str) -> bool:
    low = (text or "").strip().lower()
    if not low:
        return True
    return any(marker in low for marker in _PUNT_MARKERS)


def _history_context(messages: list[Any]) -> str | None:
    """Prior turns (before the latest user message) so the planner can reference-resolve a follow-up into a
    standalone subtask. Capped + trimmed; None when single-turn."""
    lines: list[str] = []
    for m in messages[:-1][-6:]:
        role = _msg_role(m)
        if role in ("human", "user"):
            lines.append("User: " + _msg_content(m)[:300])
        elif role == "ai":
            lines.append("Assistant: " + _msg_content(m)[:300])
    return "\n".join(lines) or None


def build_agent_graph(
    retriever: Retriever,
    settings: Settings | None = None,
    checkpointer: Any | None = None,
    specialists: dict[str, Any] | None = None,
    supervisor_router: Any | None = None,
    dispatch_planner: Any | None = None,
    model: Any | None = None,
):
    """Compile the supervisor + specialists graph.

    `specialists`, `supervisor_router`, `dispatch_planner` (async `text -> list[{query,intent}]`) and
    `model` can be injected for offline tests; when enough are provided no chat model is constructed
    (no network/key needed). Fan-out activates when a `dispatch_planner` is injected, OR on the live
    LLM path (`supervisor_router is None`) with `ENABLE_FAN_OUT`; injected-router tests keep the old flow.
    """

    settings = settings or get_settings()
    # One shared model for routing + answer generation; temp=0 (settings.llm_temperature) makes both
    # deterministic so the same question yields the same answer (Phase 1.11 consistency fix). Built only
    # when not injected and the live path needs it.
    if model is None and (specialists is None or supervisor_router is None):
        model = build_chat_model(settings, temperature=settings.llm_temperature)
    specialists = specialists or build_specialists(retriever, settings, model=model)
    fan_out = dispatch_planner is not None or (
        getattr(settings, "enable_fan_out", False) and supervisor_router is None
    )

    async def supervisor_node(state: VinUniState) -> dict:
        text = _last_user_text(state["messages"])
        if fan_out:
            # Dispatch planner (Phase 1.33): >1 assignment ⇒ fan out; 1 assignment ⇒ the single path below.
            if dispatch_planner is not None:
                plan = await dispatch_planner(text)
            else:
                plan = await plan_dispatch(
                    text, settings=settings, model=model, context=_history_context(state["messages"])
                )
            plan = plan or [{"query": text, "intent": "services"}]  # fail safe to a single services assignment
            if len(plan) > 1:
                return {"plan": plan, "intent": FANOUT_ROUTE}
            # SINGLE assignment ⇒ defer to the CALIBRATED router so single-domain routing is byte-identical to
            # fan-out OFF. The planner only decides single-vs-multi here, NOT the single-domain intent — letting
            # the planner pick it regressed 2 single-domain cases vs route_intent in the Phase 1.33 A/B.
            if supervisor_router is not None:
                intent = await supervisor_router(text)
            elif dispatch_planner is not None:
                intent = plan[0].get("intent", "services")  # offline-test convenience when no router injected
            else:
                intent = await route_intent(text, settings=settings, model=model)
            return {"intent": intent if intent in INTENTS else "services"}
        # OLD single path (unchanged when fan-out off / router injected).
        if supervisor_router is not None:
            intent = await supervisor_router(text)
        else:
            intent = await route_intent(text, settings=settings, model=model)
        return {"intent": intent if intent in INTENTS else "services"}

    def make_specialist_node(agent: Any):
        async def node(state: VinUniState) -> dict:
            # Bounded ReAct loop (Phase 1.17): cap super-steps so an agent-decided cross_lingual retry
            # can't spiral, while leaving room for native-search → retry → detail → answer.
            result = await agent.ainvoke(
                {"messages": state["messages"]},
                config={"recursion_limit": settings.agent_recursion_limit},
            )
            return {"messages": result["messages"]}

        return node

    async def _run_subtask(sub: dict) -> tuple[dict, list | None]:
        """Run ONE subtask on its specialist with a FRESH single-message context (not the full conversation).
        Per-subtask re-route (D3): an empty answer → one retry via the broad `services` specialist."""
        # Point the user-message contextvar at THIS subtask (the turn pinned it to the whole compound
        # question). The specialists' tools key structured-lookup / list-mode / cross-lingual off
        # get_user_message(); leaving it on the compound made a subtask's deterministic lookup match the wrong
        # text and punt (Phase 1.33 root-cause: dc-3part / cross-late-payment). asyncio.gather gives each
        # subtask its OWN context copy, so concurrent set_user_message calls don't clash.
        set_user_message(sub["query"])

        async def _invoke(intent: str) -> list:
            res = await specialists[intent].ainvoke(
                {"messages": [{"role": "user", "content": sub["query"]}]},
                config={"recursion_limit": settings.agent_recursion_limit},
            )
            return res.get("messages", [])

        try:
            msgs = await _invoke(sub["intent"])
            if not _last_ai_text(msgs) and sub["intent"] != "services":
                msgs = await _invoke("services")
            return sub, msgs
        except Exception:
            return sub, None  # error-isolated: this subtask becomes a named gap; the others proceed

    async def _rerun_subtask(sub: dict, prev_answer: str) -> list | None:
        """L2 reactive retry: re-run a PUNTED subtask once, feeding its failed attempt + a critique so the
        specialist reasons differently (re-search, read the full section) instead of repeating a blind query.
        The specialist stays grounded, so if the fact truly does not exist it just punts again and the caller
        keeps the original — a retry can recover a real value but can't fabricate one."""
        set_user_message(sub["query"])  # key the retry's tools off the subtask, not the leaked compound
        critique = (
            f"{sub['query']}\n\n"
            f'[Retry note: a previous search answered "{prev_answer[:300]}" and did NOT provide the specific '
            "value asked. This information very likely EXISTS in VinUni's official documents (academic calendar "
            "/ tariff / regulations). Search with DIFFERENT terms and READ the full relevant section, then "
            "state the specific value. Answer in the question's language. If it truly does not exist, say so.]"
        )
        try:
            res = await specialists[sub["intent"]].ainvoke(
                {"messages": [{"role": "user", "content": critique}]},
                config={"recursion_limit": settings.agent_recursion_limit},
            )
            return res.get("messages", [])
        except Exception:
            return None

    async def fanout_node(state: VinUniState) -> dict:
        plan = state.get("plan") or []
        text = _last_user_text(state["messages"])
        results = await asyncio.gather(*[_run_subtask(s) for s in plan])

        # L2 reactive completeness (cap=1 outer pass): re-run any subtask that PUNTED, keeping the satisfactory
        # subtasks unchanged; accept a retry only if it actually produced a non-punt answer. Guarded so the
        # common (no-punt) case costs zero extra calls.
        async def _maybe_retry(sub: dict, msgs: list | None) -> tuple[dict, list | None]:
            if _is_punt(_last_ai_text(msgs) if msgs else ""):
                retry = await _rerun_subtask(sub, _last_ai_text(msgs) if msgs else "")
                if retry and not _is_punt(_last_ai_text(retry)):
                    return sub, retry
            return sub, msgs

        if any(_is_punt(_last_ai_text(m) if m else "") for _, m in results):
            results = await asyncio.gather(*[_maybe_retry(sub, msgs) for sub, msgs in results])

        tool_msgs: list[Any] = []
        parts: list[str] = []
        for sub, msgs in results:
            if not msgs or not _last_ai_text(msgs):
                parts.append(f"[{sub['intent']}] (không truy xuất được phần: {sub['query']})")
                continue
            tool_msgs += _tool_messages(msgs)
            parts.append(f"[{sub['intent']}] Hỏi: {sub['query']}\nĐáp: {_last_ai_text(msgs)}")
        syn_model = model or build_chat_model(settings, temperature=settings.llm_temperature)
        user = f"CÂU HỎI GỐC: {text}\n\nKẾT QUẢ TỪ CÁC CHUYÊN GIA:\n" + "\n\n".join(parts)
        started = time.perf_counter()
        resp = await syn_model.ainvoke(
            [{"role": "system", "content": SYNTHESIS_SYSTEM}, {"role": "user", "content": user}]
        )
        # Attribute the synthesis call in the per-turn ledger (like router/planner/audit) — it also serves
        # as a clean per-case fan-out flag (a recorded "synthesis" stage ⇔ this turn fanned out).
        record_llm_usage(
            "synthesis", settings.openrouter_chat_model, resp, (time.perf_counter() - started) * 1000
        )
        answer = AIMessage(content=resp.content if isinstance(resp.content, str) else str(resp.content))
        # Non-evicting: keep the subtasks' ToolMessages (the service layer unions citations/evidence from
        # them) and append the merged answer LAST so messages[-1] is the user-facing reply.
        return {"messages": tool_msgs + [answer]}

    builder = StateGraph(VinUniState)
    builder.add_node("supervisor", supervisor_node)
    for intent in INTENTS:
        builder.add_node(intent, make_specialist_node(specialists[intent]))
    builder.add_node(FANOUT_ROUTE, fanout_node)
    builder.add_edge(START, "supervisor")
    routes = {intent: intent for intent in INTENTS}
    routes[FANOUT_ROUTE] = FANOUT_ROUTE
    builder.add_conditional_edges("supervisor", lambda state: state.get("intent", "services"), routes)
    for intent in INTENTS:
        builder.add_edge(intent, END)
    builder.add_edge(FANOUT_ROUTE, END)
    return builder.compile(checkpointer=checkpointer)
