"""Observability primitives (Phase 1.5a).

Request-correlation id (contextvar) shared by the FastAPI middleware and the log filter, PII
redaction for logged input/output, and per-turn token/cost estimation from LangChain
`usage_metadata`. Everything here is best-effort and fail-open — it must never break a chat turn.
"""

from __future__ import annotations

import contextvars
import hashlib
import logging
import re
import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from fastapi import FastAPI, Request

logger = logging.getLogger(__name__)

# Correlation id for the current request. Set by the HTTP middleware, read by RequestIdFilter.
_request_id: contextvars.ContextVar[str | None] = contextvars.ContextVar("request_id", default=None)


def set_request_id(value: str) -> contextvars.Token:
    return _request_id.set(value)


def reset_request_id(token: contextvars.Token) -> None:
    try:
        _request_id.reset(token)
    except (ValueError, LookupError):
        # Token from a different context (e.g. reused across tasks); ignore — non-fatal.
        pass


def get_request_id() -> str | None:
    return _request_id.get()


def add_request_id_middleware(app: FastAPI) -> None:
    """Add fail-open request-id middleware to a FastAPI app."""

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        # Honor an inbound correlation id (e.g. from a gateway) or mint one; expose it on the
        # response and bind it to logs for this request. Fail-open: never block the request.
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        token = set_request_id(request_id)
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            reset_request_id(token)


# Per-turn rerank-call counter. Rerank uses raw httpx (not LangChain), so Langfuse can't trace it;
# this counter surfaces the call count in the structured turn log (proves the 1.6 fusion saving).
#
# Concurrency note: the count lives in a 1-element list MUTATED IN PLACE (never rebound after reset) so
# an increment made inside a LangGraph node task is visible to the parent turn that logs it. The reranker
# runs deep inside `agent.ainvoke`, in a task whose context is a COPY of the parent's — a rebinding
# `.set()` there is lost across the boundary (see test_contextvar_rebind_in_child_task_does_not_propagate),
# which is exactly why rerank_calls used to log 0 despite a billed rerank call. Mirrors the stage ledger.
_rerank_calls: contextvars.ContextVar[list[int] | None] = contextvars.ContextVar(
    "rerank_calls", default=None
)


def incr_rerank_count(n: int = 1) -> None:
    try:
        counter = _rerank_calls.get()
        if counter is None:
            # No reset ran (called outside a turn); this rebind only reaches the current context.
            counter = [0]
            _rerank_calls.set(counter)
        counter[0] += n
    except Exception:
        pass


def get_rerank_count() -> int:
    counter = _rerank_calls.get()
    return counter[0] if counter else 0


def reset_rerank_count() -> None:
    """Start a fresh per-turn counter. Call once at the top of a turn, in the parent context (before
    any task spawns) so child tasks inherit the binding and their in-place increments propagate back."""
    _rerank_calls.set([0])


# Per-turn flag: did the adaptive router treat this turn as a point-lookup? Surfaced in the turn log.
# Same in-place-mutation contract as the rerank counter: mark_point_lookup() runs inside the LangGraph
# tool node (a copied context), so the flag is a mutable 1-element list reset in the parent before the
# task spawns — a `.set(True)` rebind in the node would be lost and the turn log would always read False.
_point_lookup: contextvars.ContextVar[list[bool] | None] = contextvars.ContextVar(
    "point_lookup", default=None
)


def mark_point_lookup() -> None:
    try:
        flag = _point_lookup.get()
        if flag is None:
            flag = [False]
            _point_lookup.set(flag)
        flag[0] = True
    except Exception:
        pass


def get_point_lookup() -> bool:
    flag = _point_lookup.get()
    return bool(flag and flag[0])


def reset_point_lookup() -> None:
    """Start a fresh per-turn flag, in the parent context (see reset_rerank_count)."""
    _point_lookup.set([False])


# Raw user message for the current turn. Set once by the service before the agent runs, read by the
# retrieval tool so the deterministic structured lookup matches the USER's actual question rather than
# the agent's (run-to-run variable) tool-call reformulation — making the lookup fire reliably (Phase 1.19).
_user_message: contextvars.ContextVar[str | None] = contextvars.ContextVar("user_message", default=None)


def set_user_message(value: str | None) -> None:
    _user_message.set(value)


def get_user_message() -> str | None:
    return _user_message.get()


def reset_user_message() -> None:
    _user_message.set(None)


# Authenticated student identity for the current turn (Phase 5 personalization). The security core of
# the personal DB tools: set ONCE by the chat route from the VERIFIED session (never from client or
# model input) before the agent runs, then read by the read-only personal tools to hard-scope every
# query to this student's own rows (WHERE student_profile_id = <this id>). Mirrors set_user_message —
# a parent `.set()` before any task spawns is visible to the child tool tasks (which copy the binding)
# and the tools only READ it, so no mutable-list write-back is needed. Default None = anon / admin /
# no session → the personal tools refuse. The LLM is given NO parameter to name a student, so it can
# never target another student's data by construction.
@dataclass(frozen=True)
class StudentIdentity:
    student_profile_id: uuid.UUID
    user_id: uuid.UUID


_student_identity: contextvars.ContextVar[StudentIdentity | None] = contextvars.ContextVar(
    "student_identity", default=None
)


def set_student_identity(
    student_profile_id: uuid.UUID,
    user_id: uuid.UUID,
) -> contextvars.Token:
    return _student_identity.set(
        StudentIdentity(student_profile_id=student_profile_id, user_id=user_id)
    )


def get_student_identity() -> StudentIdentity | None:
    return _student_identity.get()


def reset_student_identity(token: contextvars.Token | None = None) -> None:
    """Clear the per-turn student identity. Pass the token from set_student_identity for a precise
    reset (preferred); a bare call resets to None. Always cleared in the route's finally block."""
    try:
        if token is not None:
            _student_identity.reset(token)
        else:
            _student_identity.set(None)
    except (ValueError, LookupError):
        # Token from a different context (reused across tasks); fall back to a hard clear.
        _student_identity.set(None)


# Per-turn per-stage cost/latency ledger (Phase C). A turn touches several billable stages
# (guardrail/supervisor route, query expansion, specialist answer, rerank) but `sum_token_usage` only
# sees the answer stage — so local cost UNDERCOUNTS every turn. This ledger attributes calls / tokens /
# latency / cost PER STAGE so the eval report can prove each model call is worth its latency and money.
#
# Concurrency note: the dict is MUTATED IN PLACE (never rebound after reset) so it survives LangGraph's
# task boundaries. A child task copies the contextvar *binding* (var -> the same dict object) at
# creation, so in-place mutations made inside a graph node are visible to the parent turn. A rebinding
# `.set()` inside a child task would NOT propagate back — which is exactly why `record_stage` only
# mutates and `reset_stage_ledger` (the one rebind) runs in the parent before any task spawns.
_stage_ledger: contextvars.ContextVar[dict[str, dict[str, float]] | None] = contextvars.ContextVar(
    "stage_ledger", default=None
)

_STAGE_FIELDS = ("calls", "tokens_in", "tokens_out", "latency_ms", "est_cost_usd")


def reset_stage_ledger() -> None:
    """Start a fresh per-turn ledger. Call once at the top of a turn, in the parent context."""
    _stage_ledger.set({})


def record_stage(
    name: str,
    *,
    calls: int = 1,
    tokens_in: int = 0,
    tokens_out: int = 0,
    latency_ms: float = 0.0,
    est_cost_usd: float = 0.0,
) -> None:
    """Accumulate one stage's usage into the per-turn ledger. Best-effort; never raises."""
    try:
        ledger = _stage_ledger.get()
        if ledger is None:
            # No reset ran (called outside a turn). The rebind only reaches the parent context here.
            ledger = {}
            _stage_ledger.set(ledger)
        entry = ledger.get(name)
        if entry is None:
            entry = dict.fromkeys(_STAGE_FIELDS, 0)
            ledger[name] = entry
        entry["calls"] += calls
        entry["tokens_in"] += tokens_in
        entry["tokens_out"] += tokens_out
        entry["latency_ms"] += latency_ms
        entry["est_cost_usd"] += est_cost_usd
    except Exception:
        pass


def get_stage_ledger() -> dict[str, dict[str, float]]:
    return _stage_ledger.get() or {}


def ledger_totals(ledger: dict[str, dict[str, float]] | None = None) -> dict[str, float]:
    """Sum the per-stage ledger into turn totals: tokens_in/out, est_cost_usd, latency_ms, model_calls."""
    ledger = get_stage_ledger() if ledger is None else ledger
    tokens_in = tokens_out = model_calls = 0
    est_cost = latency_ms = 0.0
    for entry in ledger.values():
        tokens_in += int(entry.get("tokens_in") or 0)
        tokens_out += int(entry.get("tokens_out") or 0)
        model_calls += int(entry.get("calls") or 0)
        est_cost += float(entry.get("est_cost_usd") or 0.0)
        latency_ms += float(entry.get("latency_ms") or 0.0)
    return {
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "model_calls": model_calls,
        "est_cost_usd": round(est_cost, 8),
        "latency_ms": round(latency_ms, 1),
    }


def redact(text: str | None, keep: int = 24) -> str:
    """Mask free text for logs: keep a short prefix, append length + content hash so identical
    inputs are still correlatable without storing the PII itself."""
    if not text:
        return ""
    text = str(text)
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:8]
    if len(text) <= keep:
        return f"{text} [len={len(text)} sha={digest}]"
    return f"{text[:keep]}… [len={len(text)} sha={digest}]"


# Per-1M-token prices (input, output) in USD. ESTIMATES — keep in sync with provider pricing;
# unknown models fall back to (0, 0) so est_cost is 0 rather than wrong. Langfuse (Phase 1.5b) is
# the authoritative per-call cost source. Override is intentionally code-side to stay simple.
MODEL_PRICES_USD_PER_M: dict[str, tuple[float, float]] = {
    "openai/gpt-4o-mini": (0.15, 0.60),
    "openai/gpt-4o": (2.50, 10.00),
    "google/gemini-2.5-flash-lite": (0.10, 0.40),
    "qwen/qwen-2.5-7b-instruct": (0.04, 0.10),
    "meta-llama/llama-guard-4-12b": (0.05, 0.05),
}

# Rerank bills per "search unit" (≤100 docs/search), not per token; our candidate pool is
# ≤ retrieval_candidate_k so one rerank call ≈ one search. ESTIMATE (~$2.00 / 1k searches); unknown
# rerank models fall back to 0 so the figure is 0 rather than wrong.
RERANK_PRICES_USD_PER_CALL: dict[str, float] = {
    "cohere/rerank-v3.5": 0.002,
}


def sum_token_usage(messages: Iterable[Any]) -> tuple[int, int]:
    """Sum (input, output) tokens across LangChain messages that carry `usage_metadata`.

    Note: this only sees the LLM calls present in the graph result (the specialist answer). The
    supervisor router, query expansion, and guard calls happen outside that message list and are
    captured separately by the Langfuse callback in Phase 1.5b.
    """
    tokens_in = tokens_out = 0
    for message in messages:
        usage = getattr(message, "usage_metadata", None)
        if isinstance(usage, dict):
            tokens_in += int(usage.get("input_tokens") or 0)
            tokens_out += int(usage.get("output_tokens") or 0)
    return tokens_in, tokens_out


def estimate_cost_usd(model: str, tokens_in: int, tokens_out: int) -> float:
    price_in, price_out = MODEL_PRICES_USD_PER_M.get(model, (0.0, 0.0))
    return round((tokens_in * price_in + tokens_out * price_out) / 1_000_000, 8)


def rerank_cost_usd(model: str, calls: int = 1) -> float:
    """Estimated USD for `calls` rerank searches with `model` (see RERANK_PRICES_USD_PER_CALL)."""
    return round(RERANK_PRICES_USD_PER_CALL.get(model, 0.0) * calls, 8)


def usage_tokens(response: Any) -> tuple[int, int]:
    """Extract (input, output) tokens from a LangChain response's `usage_metadata`; (0, 0) if absent."""
    usage = getattr(response, "usage_metadata", None)
    if isinstance(usage, dict):
        return int(usage.get("input_tokens") or 0), int(usage.get("output_tokens") or 0)
    return 0, 0


def record_llm_usage(name: str, model: str, response: Any, latency_ms: float = 0.0) -> None:
    """Record one LLM stage call into the per-turn ledger (tokens from `usage_metadata`, cost from the
    price table). Best-effort: a metering failure must never break the turn."""
    try:
        tokens_in, tokens_out = usage_tokens(response)
        record_stage(
            name,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            latency_ms=latency_ms,
            est_cost_usd=estimate_cost_usd(model, tokens_in, tokens_out),
        )
    except Exception:
        pass


# --- Langfuse tracing (Phase 1.5b) ----------------------------------------------------------

_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
# Vietnamese-style phone numbers (leading 0 or +84). Deliberately NOT a generic long-digit rule —
# that would scrub fee amounts / dates / policy codes, which we *want* visible in traces.
_PHONE_RE = re.compile(r"(?:\+?84|0)\d{8,10}")
# VinUni student codes: VU25CECS005 / VU24VIB025 / D13CECS001 / D2026CECS001 (a "VU"/"D" prefix +
# 2–4 year digits + 2–6 faculty letters + 3 digits). A direct identifier of the signed-in student in
# the tool↔agent exchange — mask it in traces/logs. Anchored to this exact shape so it never scrubs
# course codes (CS102) or fee/date numbers.
_STUDENT_CODE_RE = re.compile(r"\b(?:VU|D)\d{2,4}[A-Z]{2,6}\d{3}\b")


def scrub_pii(text: str) -> str:
    """Mask direct identifiers (email, phone, student code) while leaving amounts/dates/course codes
    intact so traces stay useful for debugging. Masks only the OBSERVABILITY copy — never the live
    model input or the answer the student sees (which legitimately contains their own data)."""
    masked = _EMAIL_RE.sub("[email]", text)
    masked = _PHONE_RE.sub("[phone]", masked)
    return _STUDENT_CODE_RE.sub("[student-id]", masked)


def langfuse_mask(data: Any = None, **_: Any) -> Any:
    """Recursively scrub strings in Langfuse trace payloads before they leave the process."""
    if isinstance(data, str):
        return scrub_pii(data)
    if isinstance(data, dict):
        return {key: langfuse_mask(data=value) for key, value in data.items()}
    if isinstance(data, list):
        return [langfuse_mask(data=item) for item in data]
    return data


_langfuse_callbacks: list[Any] | None = None


def get_langfuse_callbacks(settings: Any) -> list[Any]:
    """Return a cached ``[CallbackHandler]`` when Langfuse is enabled + configured, else ``[]``.

    Fail-open: a missing key, missing package, or init error disables tracing for the process
    without ever affecting a chat turn. Result is cached so the client is initialized once.
    """
    global _langfuse_callbacks
    if _langfuse_callbacks is not None:
        return _langfuse_callbacks
    if (
        not getattr(settings, "enable_langfuse", False)
        or not getattr(settings, "langfuse_public_key", None)
        or not getattr(settings, "langfuse_secret_key", None)
    ):
        _langfuse_callbacks = []
        return _langfuse_callbacks
    try:
        from langfuse import Langfuse
        from langfuse.langchain import CallbackHandler

        Langfuse(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=getattr(settings, "langfuse_host", None) or "https://cloud.langfuse.com",
            environment=getattr(settings, "app_env", None),
            mask=langfuse_mask if getattr(settings, "log_redact_pii", True) else None,
        )
        _langfuse_callbacks = [CallbackHandler()]
        logger.info("Langfuse tracing enabled (host=%s).", getattr(settings, "langfuse_host", ""))
    except Exception:
        logger.warning("Langfuse init failed; tracing disabled for this process.", exc_info=True)
        _langfuse_callbacks = []
    return _langfuse_callbacks


def reset_langfuse_for_tests() -> None:
    """Clear the cached handler so tests can re-evaluate get_langfuse_callbacks."""
    global _langfuse_callbacks
    _langfuse_callbacks = None
