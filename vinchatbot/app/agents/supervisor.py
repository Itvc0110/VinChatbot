"""Intent router (supervisor) for the multi-agent graph.

Uses a cheap LLM call when an OpenRouter key is available, with a deterministic keyword
heuristic as fallback so routing stays usable offline and in tests.
"""

from __future__ import annotations

import json
import logging
import re
import time

from vinchatbot.app.agents.guardrails import normalize_for_matching
from vinchatbot.app.agents.prompts import DISPATCH_SYSTEM, SUPERVISOR_SYSTEM, SUPERVISOR_SYSTEM_V2
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


# --- Phase 1.33: dispatch planner (fan-out) ---------------------------------------------------------------

def _parse_plan(content: str) -> list[dict] | None:
    """Parse the dispatch planner's JSON list of {query, intent} assignments. Tolerant of code fences/prose:
    grabs the first JSON array. Validates each item (non-empty query, intent in INTENTS). Returns None if
    nothing valid parses, so the caller fails SAFE to a single assignment."""
    match = re.search(r"\[.*\]", content, re.DOTALL)
    if not match:
        return None
    try:
        arr = json.loads(match.group(0))
    except Exception:
        return None
    if not isinstance(arr, list):
        return None
    plan: list[dict] = []
    for item in arr:
        if not isinstance(item, dict):
            continue
        query = item.get("query")
        intent = (item.get("intent") or "").strip().lower() if isinstance(item.get("intent"), str) else ""
        if isinstance(query, str) and query.strip() and intent in INTENTS:
            plan.append({"query": query.strip(), "intent": intent})
    return plan or None


def _single_plan(message: str) -> list[dict]:
    """Fail-safe / single-domain plan: one assignment = the whole question, heuristic intent."""
    return [{"query": message, "intent": classify_intent_heuristic(message)}]


def _looks_multi(message: str) -> bool:
    """Cheap signal that a question MIGHT be compound/ambiguous (two asks, or a second part with no domain
    keyword) → do NOT fast-path; let the planner LLM decide. A coordinating 'and'/'và' or a second '?' is the
    tell. Over-triggering is harmless (the planner just returns SINGLE); UNDER-triggering hijacks fan-out."""
    low = (message or "").lower()
    return " and " in low or " và " in low or low.count("?") >= 2


async def plan_dispatch(
    message: str, settings: Settings | None = None, model=None, context: str | None = None
) -> list[dict]:
    """Return a DISPATCH PLAN — a list of {query, intent} assignments (Phase 1.33 fan-out).

    len==1  → SINGLE: the existing single-specialist path (the ~90%), byte-identical downstream.
    len>1   → DECOMPOSE (distinct subtasks) or HEDGE (same question to ≥2 candidate specialists), dispatched
              in parallel + merged by the synthesis node.

    Tier-0: a confident single-domain keyword signal → SINGLE without the LLM (same fast-path route_intent uses).
    Tier-1: the planner LLM (DISPATCH_SYSTEM) emits the plan. Any parse/validation failure or no key → fail
    SAFE to a single assignment. `context` (optional pre-formatted prior turns) enables reference resolution."""
    settings = settings or get_settings()
    cap = max(1, getattr(settings, "fan_out_max_subtasks", 3))

    # Tier-0 fast-path: skip the LLM ONLY for an UNAMBIGUOUS single-domain question — ≤1 domain has keyword
    # hits AND no compound signal. A multi-keyword or 'and'/'?'-compound question goes to the planner. (The old
    # classify_intent_confident fired on compounds with a strong single-domain keyword count and short-circuited
    # decompose/hedge before the LLM was even called — caught by manual inspection, Phase 1.33.)
    scores = _intent_scores(message)
    nonzero = [k for k, v in scores.items() if v > 0]
    if not _looks_multi(message) and len(nonzero) <= 1:
        return [{"query": message, "intent": nonzero[0] if nonzero else "services"}]
    if not settings.openrouter_api_key:
        return _single_plan(message)
    try:
        model = model or build_chat_model(
            settings, model=(settings.planner_model or None), temperature=0.0
        )
        user = message if not context else f"PRIOR TURNS:\n{context}\n\nCURRENT MESSAGE:\n{message}"
        started = time.perf_counter()
        response = await model.ainvoke(
            [{"role": "system", "content": DISPATCH_SYSTEM}, {"role": "user", "content": user}]
        )
        record_llm_usage(
            "supervisor", settings.openrouter_chat_model, response, (time.perf_counter() - started) * 1000
        )
        content = response.content if isinstance(response.content, str) else str(response.content)
        plan = _parse_plan(content)
        if plan:
            plan = plan[:cap]
            # Same-specialist collapse (Phase 1.33): a multi-assignment plan where EVERY part routes to the
            # SAME specialist is an OVER-FIRE — one specialist answers all facets better from the whole
            # question's context than from narrow split subtasks (split subtasks lose coverage / break the
            # citation / punt). Measured: 4/5 full-199 scored regressions were all-same-intent splits. Collapse
            # to SINGLE (whole question) → the byte-identical single path. Genuine DECOMPOSE/HEDGE always span
            # ≥2 DISTINCT intents, so they are untouched. Deterministic — does not rely on the LLM's prompt rule.
            if len(plan) > 1 and len({item["intent"] for item in plan}) == 1:
                return [{"query": message, "intent": plan[0]["intent"]}]
            return plan
    except Exception:
        logger.debug("Dispatch planner fell back to single assignment.", exc_info=True)
    return _single_plan(message)
