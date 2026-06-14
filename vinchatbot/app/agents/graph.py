"""LangGraph multi-agent graph: supervisor routes to one specialist per turn.

Flow: START -> supervisor (sets intent) -> <specialist> -> END.

Input guarding and output guarding (sensitive/citation/faithfulness) are applied at the
service layer (VinUniAgentService) on the graph's message output, so the compiled graph
keeps the same `ainvoke({"messages": [...]}, config=...) -> {"messages": [...]}` contract
the rest of the app already depends on.
"""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, MessagesState, StateGraph

from vinchatbot.app.agents.specialists import build_specialists
from vinchatbot.app.agents.supervisor import INTENTS, route_intent
from vinchatbot.app.core.config import Settings, get_settings
from vinchatbot.app.llm.openrouter_chat import build_chat_model
from vinchatbot.app.rag.retriever import Retriever


class VinUniState(MessagesState):
    intent: str


def _last_user_text(messages: list[Any]) -> str:
    for message in reversed(messages):
        if isinstance(message, dict):
            if message.get("role") in ("user", "human"):
                content = message.get("content", "")
                return content if isinstance(content, str) else str(content)
            continue
        if getattr(message, "type", None) in ("human", "user"):
            content = getattr(message, "content", "")
            return content if isinstance(content, str) else str(content)
    if messages:
        last = messages[-1]
        content = last.get("content", "") if isinstance(last, dict) else getattr(last, "content", "")
        return content if isinstance(content, str) else str(content)
    return ""


def build_agent_graph(
    retriever: Retriever,
    settings: Settings | None = None,
    checkpointer: Any | None = None,
    specialists: dict[str, Any] | None = None,
    supervisor_router: Any | None = None,
):
    """Compile the supervisor + specialists graph.

    `specialists` and `supervisor_router` can be injected for offline tests; when both are
    provided no chat model is constructed (no network/key needed).
    """

    settings = settings or get_settings()
    needs_model = specialists is None or supervisor_router is None
    model = build_chat_model(settings) if needs_model else None
    specialists = specialists or build_specialists(retriever, settings, model=model)

    async def supervisor_node(state: VinUniState) -> dict:
        text = _last_user_text(state["messages"])
        if supervisor_router is not None:
            intent = await supervisor_router(text)
        else:
            intent = await route_intent(text, settings=settings, model=model)
        return {"intent": intent if intent in INTENTS else "services"}

    def make_specialist_node(agent: Any):
        async def node(state: VinUniState) -> dict:
            result = await agent.ainvoke({"messages": state["messages"]})
            return {"messages": result["messages"]}

        return node

    builder = StateGraph(VinUniState)
    builder.add_node("supervisor", supervisor_node)
    for intent in INTENTS:
        builder.add_node(intent, make_specialist_node(specialists[intent]))
    builder.add_edge(START, "supervisor")
    builder.add_conditional_edges(
        "supervisor",
        lambda state: state.get("intent", "services"),
        {intent: intent for intent in INTENTS},
    )
    for intent in INTENTS:
        builder.add_edge(intent, END)
    return builder.compile(checkpointer=checkpointer)
