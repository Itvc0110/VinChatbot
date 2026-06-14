"""Specialist agents for the multi-agent graph.

One ReAct agent per intent, each with its own prompt and a focused subset of the
retrieval tools built by build_retrieval_tools.
"""

from __future__ import annotations

from typing import Any

from vinchatbot.app.agents.prompts import (
    CALENDAR_PROMPT,
    FINANCIAL_PROMPT,
    POLICY_PROMPT,
    SERVICES_PROMPT,
)
from vinchatbot.app.agents.tools import build_retrieval_tools
from vinchatbot.app.core.config import Settings, get_settings
from vinchatbot.app.llm.openrouter_chat import build_chat_model
from vinchatbot.app.rag.retriever import Retriever

SPECIALIST_TOOLS: dict[str, set[str]] = {
    "calendar": {"search_academic_calendar", "get_source_detail"},
    "policy": {"search_policy_documents", "get_source_detail"},
    "financial": {"search_financial_regulations", "get_source_detail"},
    "services": {"search_vinuni", "get_source_detail"},
}

SPECIALIST_PROMPTS: dict[str, str] = {
    "calendar": CALENDAR_PROMPT,
    "policy": POLICY_PROMPT,
    "financial": FINANCIAL_PROMPT,
    "services": SERVICES_PROMPT,
}


def build_specialists(
    retriever: Retriever,
    settings: Settings | None = None,
    model: Any | None = None,
) -> dict[str, Any]:
    """Build one compiled ReAct agent per intent (no checkpointer; the outer graph owns memory)."""

    settings = settings or get_settings()
    try:
        from langchain.agents import create_agent
    except ImportError as exc:
        raise RuntimeError("Install langchain to build specialist agents.") from exc

    model = model or build_chat_model(settings)
    tools_by_name = {tool.name: tool for tool in build_retrieval_tools(retriever)}

    specialists: dict[str, Any] = {}
    for intent, tool_names in SPECIALIST_TOOLS.items():
        tools = [tools_by_name[name] for name in tool_names if name in tools_by_name]
        specialists[intent] = create_agent(
            model=model,
            tools=tools,
            system_prompt=SPECIALIST_PROMPTS[intent],
        )
    return specialists
