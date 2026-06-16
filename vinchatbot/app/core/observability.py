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
from collections.abc import Iterable
from typing import Any

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


# Per-turn rerank-call counter. Rerank uses raw httpx (not LangChain), so Langfuse can't trace it;
# this counter surfaces the call count in the structured turn log (proves the 1.6 fusion saving).
_rerank_calls: contextvars.ContextVar[int] = contextvars.ContextVar("rerank_calls", default=0)


def incr_rerank_count(n: int = 1) -> None:
    try:
        _rerank_calls.set(_rerank_calls.get() + n)
    except Exception:
        pass


def get_rerank_count() -> int:
    return _rerank_calls.get()


def reset_rerank_count() -> None:
    _rerank_calls.set(0)


# Per-turn flag: did the adaptive router treat this turn as a point-lookup? Surfaced in the turn log.
_point_lookup: contextvars.ContextVar[bool] = contextvars.ContextVar("point_lookup", default=False)


def mark_point_lookup() -> None:
    _point_lookup.set(True)


def get_point_lookup() -> bool:
    return _point_lookup.get()


def reset_point_lookup() -> None:
    _point_lookup.set(False)


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


# --- Langfuse tracing (Phase 1.5b) ----------------------------------------------------------

_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
# Vietnamese-style phone numbers (leading 0 or +84). Deliberately NOT a generic long-digit rule —
# that would scrub fee amounts / dates / policy codes, which we *want* visible in traces.
_PHONE_RE = re.compile(r"(?:\+?84|0)\d{8,10}")


def scrub_pii(text: str) -> str:
    """Mask direct identifiers (email, phone) while leaving amounts/dates intact so traces stay
    useful for debugging. The bot already refuses personal-record requests upstream."""
    return _PHONE_RE.sub("[phone]", _EMAIL_RE.sub("[email]", text))


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
