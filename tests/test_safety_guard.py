from __future__ import annotations

import asyncio
from types import SimpleNamespace

from vinchatbot.app.agents.safety_guard import _parse_openai_moderation, assess_safety


def test_parse_openai_moderation_flags_unsafe():
    payload = {"results": [{"flagged": True, "categories": {"hate": True, "violence": False}}]}
    decision = _parse_openai_moderation(payload)
    assert decision.action == "abusive_language"
    assert "hate" in decision.reason


def test_parse_openai_moderation_allows_safe():
    payload = {"results": [{"flagged": False, "categories": {}}]}
    assert _parse_openai_moderation(payload).allowed


def test_assess_safety_off_backend_is_safe():
    settings = SimpleNamespace(safety_guard_backend="off")
    assert asyncio.run(assess_safety("anything", settings)).allowed


def test_assess_safety_openai_without_key_is_safe_no_network():
    # Backend selected but no key -> must short-circuit to safe without any HTTP call.
    settings = SimpleNamespace(
        safety_guard_backend="openai_moderation",
        openai_api_key=None,
        openai_base_url="https://api.openai.com/v1",
        openai_moderation_model="omni-moderation-latest",
    )
    assert asyncio.run(assess_safety("I hate everyone", settings)).allowed
