from __future__ import annotations

import json
import logging
from types import SimpleNamespace

from fastapi.testclient import TestClient

from vinchatbot.app.core.logging import JsonFormatter, RequestIdFilter
from vinchatbot.app.core.observability import (
    estimate_cost_usd,
    get_langfuse_callbacks,
    redact,
    reset_langfuse_for_tests,
    reset_request_id,
    scrub_pii,
    set_request_id,
    sum_token_usage,
)
from vinchatbot.app.main import create_app


def _record(msg: str = "hello", **extra) -> logging.LogRecord:
    record = logging.LogRecord("test", logging.INFO, "p", 1, msg, None, None)
    for key, value in extra.items():
        setattr(record, key, value)
    return record


def test_json_formatter_emits_json_with_request_id():
    token = set_request_id("rid-123")
    record = _record("turn happened")
    RequestIdFilter().filter(record)
    try:
        data = json.loads(JsonFormatter().format(record))
    finally:
        reset_request_id(token)
    assert data["msg"] == "turn happened"
    assert data["request_id"] == "rid-123"
    assert data["level"] == "INFO"


def test_json_formatter_includes_extra_fields():
    record = _record("chat_turn", intent="calendar", latency_ms=42, est_cost_usd=0.0001)
    RequestIdFilter().filter(record)
    data = json.loads(JsonFormatter().format(record))
    assert data["intent"] == "calendar"
    assert data["latency_ms"] == 42
    assert data["est_cost_usd"] == 0.0001


def test_redact_masks_long_content():
    secret = "A" * 100
    out = redact(secret)
    assert out.count("A") <= 24  # only the short prefix survives
    assert "len=100" in out and "sha=" in out


def test_redact_empty_is_empty():
    assert redact("") == ""
    assert redact(None) == ""


def test_sum_token_usage_only_counts_messages_with_usage():
    messages = [
        SimpleNamespace(usage_metadata={"input_tokens": 1000, "output_tokens": 500}),
        SimpleNamespace(content="no usage here"),
        SimpleNamespace(usage_metadata={"input_tokens": 200, "output_tokens": 100}),
    ]
    assert sum_token_usage(messages) == (1200, 600)


def test_estimate_cost_known_and_unknown_model():
    cost = estimate_cost_usd("openai/gpt-4o-mini", 1000, 500)
    assert cost == round((1000 * 0.15 + 500 * 0.60) / 1_000_000, 8)
    assert estimate_cost_usd("some/unknown-model", 1000, 500) == 0.0


def test_langfuse_disabled_returns_no_callbacks():
    reset_langfuse_for_tests()
    settings = SimpleNamespace(
        enable_langfuse=False, langfuse_public_key=None, langfuse_secret_key=None
    )
    assert get_langfuse_callbacks(settings) == []
    reset_langfuse_for_tests()


def test_langfuse_enabled_without_keys_is_fail_open():
    reset_langfuse_for_tests()
    settings = SimpleNamespace(
        enable_langfuse=True, langfuse_public_key=None, langfuse_secret_key=None
    )
    assert get_langfuse_callbacks(settings) == []
    reset_langfuse_for_tests()


def test_scrub_pii_masks_email_and_phone_but_keeps_amounts():
    out = scrub_pii("Mail a.b@vinuni.edu.vn or call 0901234567; tuition is 349650000 VND in 2026")
    assert "[email]" in out
    assert "[phone]" in out
    assert "349650000" in out  # fee preserved
    assert "2026" in out  # year preserved


def test_request_id_header_is_set_and_honored():
    client = TestClient(create_app())

    minted = client.get("/health")
    assert minted.status_code == 200
    assert minted.headers.get("X-Request-ID")

    echoed = client.get("/health", headers={"X-Request-ID": "abc123"})
    assert echoed.headers.get("X-Request-ID") == "abc123"
