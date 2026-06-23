from __future__ import annotations

import asyncio
from types import SimpleNamespace

from vinchatbot.app.agents.supervisor import (
    classify_intent_confident,
    classify_intent_heuristic,
    route_intent,
)


class _BoomModel:
    """Fails if invoked — proves a confident route skips the LLM."""

    async def ainvoke(self, messages):
        raise AssertionError("LLM must not be called for a high-confidence keyword route")


# ---- classify_intent_confident (Phase 1.23c deterministic gate) ----------------------------

def test_confident_routes_strong_unambiguous_signal():
    assert classify_intent_confident("tuition fee and tariff for the program") == "financial"  # 3 financial
    assert classify_intent_confident("code of conduct and academic integrity policy") == "policy"


def test_confident_none_when_weak_or_ambiguous():
    assert classify_intent_confident("deadline") is None  # single calendar hit (<2) → defer to LLM
    assert classify_intent_confident("library opening hours") is None  # services-ish, no strong signal
    # the courseeval mis-route case: no strong keyword → must defer to the (hardened) LLM, not guess
    assert classify_intent_confident("Có tổ chức đánh giá cuối khóa cho mỗi môn không?") is None
    assert classify_intent_confident("when is the course evaluation period for Fall 2026?") is None


# ---- route_intent v2 gating ----------------------------------------------------------------

def test_router_v2_confident_skips_llm():
    settings = SimpleNamespace(enable_router_v2=True, openrouter_api_key="sk-test")
    intent = asyncio.run(route_intent("tuition fee tariff per semester", settings, _BoomModel()))
    assert intent == "financial"  # deterministic; _BoomModel proves the LLM was not called


def test_router_v2_off_is_unchanged():
    # v2 off + no API key → the existing heuristic path, byte-identical to before.
    settings = SimpleNamespace(enable_router_v2=False, openrouter_api_key=None)
    assert asyncio.run(route_intent("tuition fee tariff", settings, None)) == "financial"
    assert classify_intent_heuristic("random unrelated question") == "services"
