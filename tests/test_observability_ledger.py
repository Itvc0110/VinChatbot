from __future__ import annotations

import asyncio
import contextvars
from types import SimpleNamespace

from vinchatbot.app.core.observability import (
    get_stage_ledger,
    ledger_totals,
    record_llm_usage,
    record_stage,
    rerank_cost_usd,
    reset_stage_ledger,
    usage_tokens,
)


def test_record_stage_accumulates_per_stage_and_reset_clears():
    reset_stage_ledger()
    record_stage("supervisor", tokens_in=100, tokens_out=20, latency_ms=12.0, est_cost_usd=0.001)
    record_stage("supervisor", tokens_in=50, tokens_out=10, latency_ms=8.0, est_cost_usd=0.0005)
    record_stage("rerank", latency_ms=30.0, est_cost_usd=0.002)

    ledger = get_stage_ledger()
    assert ledger["supervisor"]["calls"] == 2
    assert ledger["supervisor"]["tokens_in"] == 150
    assert ledger["supervisor"]["tokens_out"] == 30
    assert ledger["supervisor"]["latency_ms"] == 20.0
    assert round(ledger["supervisor"]["est_cost_usd"], 6) == 0.0015
    assert ledger["rerank"]["calls"] == 1
    assert ledger["rerank"]["tokens_in"] == 0

    reset_stage_ledger()
    assert get_stage_ledger() == {}


def test_ledger_totals_sums_all_stages():
    reset_stage_ledger()
    record_stage("supervisor", tokens_in=100, tokens_out=20, latency_ms=10.0, est_cost_usd=0.001)
    record_stage("answer", calls=2, tokens_in=900, tokens_out=300, latency_ms=400.0, est_cost_usd=0.02)
    record_stage("rerank", latency_ms=30.0, est_cost_usd=0.002)

    totals = ledger_totals()
    assert totals["tokens_in"] == 1000
    assert totals["tokens_out"] == 320
    assert totals["model_calls"] == 4  # 1 + 2 + 1
    assert round(totals["est_cost_usd"], 6) == 0.023
    assert totals["latency_ms"] == 440.0


def test_ledger_totals_empty_ledger_is_zeroed():
    reset_stage_ledger()
    totals = ledger_totals()
    assert totals == {
        "tokens_in": 0,
        "tokens_out": 0,
        "model_calls": 0,
        "est_cost_usd": 0.0,
        "latency_ms": 0.0,
    }


def test_record_llm_usage_extracts_tokens_and_prices_known_model():
    reset_stage_ledger()
    response = SimpleNamespace(usage_metadata={"input_tokens": 1000, "output_tokens": 500})
    record_llm_usage("llm_guard", "qwen/qwen-2.5-7b-instruct", response, latency_ms=15.0)

    entry = get_stage_ledger()["llm_guard"]
    assert entry["tokens_in"] == 1000
    assert entry["tokens_out"] == 500
    assert entry["latency_ms"] == 15.0
    # qwen price (0.04, 0.10) per 1M
    assert entry["est_cost_usd"] == round((1000 * 0.04 + 500 * 0.10) / 1_000_000, 8)


def test_record_llm_usage_unknown_model_costs_zero_but_still_records_tokens():
    reset_stage_ledger()
    response = SimpleNamespace(usage_metadata={"input_tokens": 10, "output_tokens": 5})
    record_llm_usage("supervisor", "some/unknown-model", response)
    entry = get_stage_ledger()["supervisor"]
    assert entry["tokens_in"] == 10
    assert entry["est_cost_usd"] == 0.0


def test_usage_tokens_handles_missing_metadata():
    assert usage_tokens(SimpleNamespace(usage_metadata={"input_tokens": 7, "output_tokens": 3})) == (7, 3)
    assert usage_tokens(SimpleNamespace(content="no usage")) == (0, 0)
    assert usage_tokens(object()) == (0, 0)


def test_rerank_cost_known_and_unknown():
    assert rerank_cost_usd("cohere/rerank-v3.5") == 0.002
    assert rerank_cost_usd("cohere/rerank-v3.5", calls=3) == 0.006
    assert rerank_cost_usd("unknown/reranker") == 0.0


def test_record_stage_is_fail_open_on_bad_input():
    reset_stage_ledger()
    # A non-numeric token value would raise inside the accumulation; it must be swallowed.
    record_stage("answer", tokens_in="not-a-number")  # type: ignore[arg-type]
    # No exception propagated; the stage entry exists (best-effort).
    assert "answer" in get_stage_ledger()


def test_record_llm_usage_never_raises_on_bad_response():
    reset_stage_ledger()
    # Should not raise even if the response is None / malformed.
    record_llm_usage("supervisor", "openai/gpt-4o-mini", None)
    record_llm_usage("supervisor", "openai/gpt-4o-mini", SimpleNamespace(usage_metadata="bad"))


def test_ledger_survives_create_task_boundary():
    """The load-bearing assumption: a stage recorded INSIDE a spawned task (how LangGraph may run a
    node) is visible to the parent turn, because record_stage mutates the ledger dict IN PLACE and
    reset_stage_ledger binds it in the parent BEFORE the task spawns."""

    async def child() -> None:
        record_stage("answer", tokens_in=10, est_cost_usd=0.001)

    async def parent() -> dict:
        reset_stage_ledger()  # bind the dict in the parent context first
        await asyncio.create_task(child())  # child gets a COPIED context (same dict object)
        return get_stage_ledger()

    ledger = asyncio.run(parent())
    assert ledger["answer"]["tokens_in"] == 10


def test_contextvar_rebind_in_child_task_does_not_propagate():
    """Documents WHY record_stage mutates in place instead of `.set()`-rebinding: a rebind inside a
    spawned task is invisible to the parent, which would silently lose stage data."""
    var: contextvars.ContextVar[str | None] = contextvars.ContextVar("probe", default=None)

    async def child() -> None:
        var.set("child")  # rebind in the child's copied context

    async def parent() -> str | None:
        var.set("parent")
        await asyncio.create_task(child())
        return var.get()

    assert asyncio.run(parent()) == "parent"
