"""Content-safety guard tier (pluggable API backend).

Default backend: OpenAI `omni-moderation-latest` (free/cheapest). Alternative: Llama Guard 4
via OpenRouter. Invoked only on non-confident turns (see `resolve_guardrail_decision`), so
most turns never reach it. Fails open (safe) on any error or missing credential — the
always-on regex tier is the safety floor.
"""

from __future__ import annotations

import logging
import time

import httpx

from vinchatbot.app.agents.guardrails import GuardrailDecision
from vinchatbot.app.core.config import Settings, get_settings
from vinchatbot.app.core.observability import record_llm_usage, record_stage

logger = logging.getLogger(__name__)

_SAFE = GuardrailDecision(action="allow", reason="safety guard: safe")


def _parse_openai_moderation(payload: dict) -> GuardrailDecision:
    result = (payload.get("results") or [{}])[0]
    if result.get("flagged"):
        categories = [name for name, on in (result.get("categories") or {}).items() if on]
        return GuardrailDecision(
            action="abusive_language",
            reason=f"OpenAI moderation flagged: {', '.join(categories) or 'unsafe'}",
        )
    return _SAFE


async def assess_safety(text: str, settings: Settings | None = None) -> GuardrailDecision:
    """Return an allow/block decision from the configured content-safety backend."""

    settings = settings or get_settings()
    backend = (settings.safety_guard_backend or "off").lower()
    if backend == "off" or not text.strip():
        return _SAFE
    try:
        if backend == "openai_moderation":
            return await _openai_moderation(text, settings)
        if backend == "llama_guard":
            return await _llama_guard(text, settings)
    except Exception:
        # Fail-open (don't hard-fail every turn on a transient moderation outage), but log at WARNING so
        # a PERSISTENT failure — e.g. an invalid/expired key returning 401 — is visible, not silent.
        logger.warning("Safety guard (%s) failed; allowing this turn.", backend, exc_info=True)
    return _SAFE


async def _openai_moderation(text: str, settings: Settings) -> GuardrailDecision:
    if not settings.openai_api_key:
        logger.debug("OPENAI_API_KEY not set; openai_moderation safety tier inactive.")
        return _SAFE
    headers = {"Authorization": f"Bearer {settings.openai_api_key}", "Content-Type": "application/json"}
    started = time.perf_counter()
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(
            f"{settings.openai_base_url.rstrip('/')}/moderations",
            headers=headers,
            json={"model": settings.openai_moderation_model, "input": text},
        )
        response.raise_for_status()
        payload = response.json()
    # omni-moderation is free and returns no token usage — record the call + latency only.
    record_stage("safety_moderation", latency_ms=(time.perf_counter() - started) * 1000)
    return _parse_openai_moderation(payload)


async def _llama_guard(text: str, settings: Settings) -> GuardrailDecision:
    from vinchatbot.app.llm.openrouter_chat import build_chat_model

    model = build_chat_model(settings, model=settings.llama_guard_model, temperature=0.0)
    started = time.perf_counter()
    response = await model.ainvoke([{"role": "user", "content": text}])
    record_llm_usage(
        "safety_moderation", settings.llama_guard_model, response, (time.perf_counter() - started) * 1000
    )
    content = response.content if isinstance(response.content, str) else str(response.content)
    if "unsafe" in content.lower():
        return GuardrailDecision(
            action="abusive_language",
            reason=f"Llama Guard flagged: {content.strip()[:80]}",
        )
    return _SAFE
