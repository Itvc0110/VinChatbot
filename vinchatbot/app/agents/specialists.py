"""Specialist agents for the multi-agent graph.

One ReAct agent per intent, each with its own prompt and a focused subset of the
retrieval tools built by build_retrieval_tools.
"""

from __future__ import annotations

from typing import Any

from vinchatbot.app.agents.personal_tools import build_personal_tools
from vinchatbot.app.agents.prompts import (
    CALENDAR_PROMPT,
    FINANCIAL_PROMPT,
    PERSONAL_PROMPT,
    POINT_LOOKUP_SUFFIX,
    POLICY_PROMPT,
    SERVICES_PROMPT,
)
from vinchatbot.app.agents.tools import build_retrieval_tools
from vinchatbot.app.core.config import Settings, get_settings
from vinchatbot.app.llm.openrouter_chat import build_chat_model
from vinchatbot.app.rag.retriever import Retriever

# The dedicated personalization specialist. Built ONLY when a read-only app DB pool is supplied, so the
# general RAG path (calendar/policy/financial/services) is unchanged when the DB is absent (tests/offline).
PERSONAL_INTENT = "personal"

SPECIALIST_TOOLS: dict[str, set[str]] = {
    "calendar": {"search_academic_calendar", "get_source_detail"},
    "policy": {"search_policy_documents", "search_forms", "get_source_detail"},
    "financial": {"search_financial_regulations", "get_source_detail"},
    "services": {"search_vinuni", "search_forms", "get_source_detail"},
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
    personal_pool: Any | None = None,
) -> dict[str, Any]:
    """Build one compiled ReAct agent per intent (no checkpointer; the outer graph owns memory).

    When `personal_pool` (the READ-ONLY app DB pool) is supplied, also build the dedicated "personal"
    specialist with the read-only, session-scoped DB tools. When it is absent (offline/tests, or no
    DB configured) the general specialists are returned unchanged and there is no "personal" agent.
    """

    settings = settings or get_settings()
    try:
        from langchain.agents import create_agent
    except ImportError as exc:
        raise RuntimeError("Install langchain to build specialist agents.") from exc

    model = model or build_chat_model(settings)
    tools_by_name = {tool.name: tool for tool in build_retrieval_tools(retriever)}

    # Adaptive retrieval (Phase 1.7): the point-lookup specialists read full sections, so they get a
    # strict "answer only the asked value" suffix to stop them over-sharing neighbouring rows.
    strict_intents = {"calendar", "financial"} if settings.enable_adaptive_retrieval else set()

    specialists: dict[str, Any] = {}
    for intent, tool_names in SPECIALIST_TOOLS.items():
        tools = [tools_by_name[name] for name in tool_names if name in tools_by_name]
        system_prompt = SPECIALIST_PROMPTS[intent]
        if intent in strict_intents:
            system_prompt = system_prompt + POINT_LOOKUP_SUFFIX
        specialists[intent] = create_agent(
            model=model,
            tools=tools,
            system_prompt=system_prompt,
        )

    # The personalization specialist owns the ONLY DB tools; built only when a pool is available.
    if personal_pool is not None:
        specialists[PERSONAL_INTENT] = create_agent(
            model=model,
            tools=build_personal_tools(personal_pool, settings),
            system_prompt=PERSONAL_PROMPT,
        )

    return specialists
