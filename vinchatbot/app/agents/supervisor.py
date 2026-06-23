"""Intent router (supervisor) for the multi-agent graph.

Uses a cheap LLM call when an OpenRouter key is available, with a deterministic keyword
heuristic as fallback so routing stays usable offline and in tests.
"""

from __future__ import annotations

import logging
import re
import time

from vinchatbot.app.agents.guardrails import normalize_for_matching
from vinchatbot.app.agents.prompts import SUPERVISOR_SYSTEM, SUPERVISOR_SYSTEM_V2
from vinchatbot.app.core.config import Settings, get_settings
from vinchatbot.app.core.observability import record_llm_usage
from vinchatbot.app.llm.openrouter_chat import build_chat_model

logger = logging.getLogger(__name__)

INTENTS = ("calendar", "policy", "financial", "services")

# Keyword sets are accent-stripped to match normalize_for_matching output.
_CALENDAR_TERMS = (
    "calendar", "lich hoc", "hoc ky", "semester", "deadline", "han ", "drop", "huy mon",
    "rut mon", "registration", "dang ky", "exam", "thi ", "instruction", "giang day",
    "holiday", "nghi le", "term", "fall", "spring", "summer", "academic year", "nam hoc",
)
_FINANCIAL_TERMS = (
    "tuition", "hoc phi", "fee", "le phi", "tariff", "phat", "fine", "scholarship",
    "hoc bong", "financial aid", "ho tro tai chinh", "refund", "hoan tien", "payment",
    "thanh toan", "phi ",
)
_POLICY_TERMS = (
    "policy", "quy dinh", "quy che", "regulation", "code of conduct", "conduct", "ky luat",
    "academic integrity", "liem chinh", "appeal", "khieu nai", "leave of absence", "bao luu",
    "withdrawal", "procedure", "thu tuc", "quy trinh", "rights", "quyen loi", "nghia vu",
)


def _intent_scores(message: str) -> dict[str, int]:
    normalized = normalize_for_matching(message)

    def hits(terms: tuple[str, ...]) -> int:
        return sum(1 for term in terms if term.strip() and term.strip() in normalized)

    return {
        "calendar": hits(_CALENDAR_TERMS),
        "financial": hits(_FINANCIAL_TERMS),
        "policy": hits(_POLICY_TERMS),
    }


def classify_intent_heuristic(message: str) -> str:
    scores = _intent_scores(message)
    best = max(scores, key=lambda key: scores[key])
    return best if scores[best] > 0 else "services"


def classify_intent_confident(message: str) -> str | None:
    """Deterministic high-confidence routing (Phase 1.23c): return an intent ONLY when the keyword signal is
    strong and unambiguous — the winning category has >=2 hits AND a clear lead over the runner-up. Otherwise
    None → let the (hardened) LLM decide. Keeps the LLM out of obviously-keyworded routings; the LLM cache
    covers determinism for the rest."""
    scores = _intent_scores(message)
    ranked = sorted(scores.values(), reverse=True)
    top, second = ranked[0], ranked[1]
    if top >= 2 and top > second:
        return max(scores, key=lambda key: scores[key])
    return None


def _parse_intent(content: str) -> str | None:
    normalized = normalize_for_matching(content)
    for intent in INTENTS:
        if re.search(rf'"?intent"?\s*:\s*"?{intent}"?', normalized):
            return intent
    for intent in INTENTS:  # bare-word fallback if the model skipped JSON
        if re.search(rf"(?<!\w){intent}(?!\w)", normalized):
            return intent
    return None


async def route_intent(message: str, settings: Settings | None = None, model=None) -> str:
    """Return one of INTENTS for the given message."""

    settings = settings or get_settings()
    router_v2 = getattr(settings, "enable_router_v2", False)
    # Router v2 (1.23c): deterministic-first — a strong, unambiguous keyword signal routes WITHOUT the LLM.
    if router_v2:
        confident = classify_intent_confident(message)
        if confident is not None:
            return confident
    if not settings.openrouter_api_key:
        return classify_intent_heuristic(message)
    system = SUPERVISOR_SYSTEM_V2 if router_v2 else SUPERVISOR_SYSTEM
    try:
        model = model or build_chat_model(settings, temperature=0.0)
        started = time.perf_counter()
        response = await model.ainvoke(
            [
                {"role": "system", "content": system},
                {"role": "user", "content": message},
            ]
        )
        record_llm_usage(
            "supervisor",
            settings.openrouter_chat_model,
            response,
            (time.perf_counter() - started) * 1000,
        )
        content = response.content if isinstance(response.content, str) else str(response.content)
        return _parse_intent(content) or classify_intent_heuristic(message)
    except Exception:
        logger.debug("Supervisor routing fell back to heuristic.", exc_info=True)
        return classify_intent_heuristic(message)
