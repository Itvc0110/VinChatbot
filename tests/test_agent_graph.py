from __future__ import annotations

import asyncio
from types import SimpleNamespace

from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver

from vinchatbot.app.agents.graph import build_agent_graph
from vinchatbot.app.agents.guardrails import assess_faithfulness
from vinchatbot.app.agents.supervisor import INTENTS, classify_intent_heuristic


def _fake_specialist(name: str):
    class _Agent:
        async def ainvoke(self, payload, config=None):
            return {"messages": [*payload["messages"], AIMessage(content=f"answer from {name}")]}

    return _Agent()


def _build_test_graph(route_to: str):
    async def router(_text: str) -> str:
        return route_to

    specialists = {intent: _fake_specialist(intent) for intent in INTENTS}
    return build_agent_graph(
        retriever=None,
        settings=SimpleNamespace(agent_recursion_limit=3, llm_temperature=0.0),
        specialists=specialists,
        supervisor_router=router,
        checkpointer=InMemorySaver(),
    )


def _run_graph(awaitable):
    return asyncio.run(asyncio.wait_for(awaitable, timeout=2.0))


def test_graph_routes_to_selected_specialist():
    graph = _build_test_graph("calendar")
    out = _run_graph(
        graph.ainvoke(
            {"messages": [{"role": "user", "content": "Hạn hủy môn Fall 2026?"}]},
            config={"configurable": {"thread_id": "t1"}},
        )
    )
    assert out["intent"] == "calendar"
    assert "answer from calendar" in out["messages"][-1].content


def test_graph_persists_memory_across_turns():
    graph = _build_test_graph("services")
    config = {"configurable": {"thread_id": "mem"}}
    _run_graph(graph.ainvoke({"messages": [{"role": "user", "content": "first"}]}, config=config))
    out = _run_graph(
        graph.ainvoke({"messages": [{"role": "user", "content": "second"}]}, config=config)
    )
    # both turns' human messages plus both specialist replies accumulate in the thread
    assert len(out["messages"]) >= 4


def test_heuristic_routing_covers_each_intent():
    assert classify_intent_heuristic("Hạn hủy môn Fall 2026 là khi nào?") == "calendar"
    assert classify_intent_heuristic("Học phí học kỳ này bao nhiêu?") == "financial"
    assert classify_intent_heuristic("Quy định về academic integrity là gì?") == "policy"
    assert classify_intent_heuristic("Thư viện mở cửa mấy giờ?") == "services"


def test_faithfulness_flags_unsupported_numeric_claims():
    assert assess_faithfulness("Hạn là 9 tháng 10 năm 2026.", ["Course Drop Deadline 9-Oct 2026"])
    assert not assess_faithfulness("Học phí là 999888777 VND.", ["tuition without that figure 12345"])
    # No numeric claims -> nothing to verify, treated as grounded.
    assert assess_faithfulness("Bạn nên liên hệ phòng đăng ký.", ["registrar office info"])
    # No evidence -> deferred to the citation-presence guard.
    assert assess_faithfulness("Hạn là 9 tháng 10.", [])


def test_faithfulness_ignores_citation_metadata_digits():
    # A correct prose answer must not be flagged just because its Source line carries a policy
    # code / URL digit that is metadata, not a claim (regression: LOA answer refused over "54").
    answer = (
        "The purpose of the leave of absence procedure is to provide a structured process.\n\n"
        "**Source**: Procedure for Requesting a Leave of Absence "
        "([here](https://policy.vinuni.edu.vn/all-policies/leave-2025/)) (Policy Code: VUNI.54)."
    )
    evidence = ["The purpose of the leave of absence (LOA) procedure is to provide a structured process."]
    assert assess_faithfulness(answer, evidence)  # citation digits (54, 2025) excluded
    # A genuine hallucinated body number is still caught.
    assert not assess_faithfulness("The fee is 12345 VND. **Source**: Fees (Policy Code: VUNI.54).", evidence)
