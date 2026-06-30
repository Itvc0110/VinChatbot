"""Chat-time rate limiting (Phase 1.10).

A small in-process sliding-window limiter to curb abuse / runaway cost on the public API. Off by
default (eval/CI unaffected); keyed by client IP (X-Forwarded-For aware). Fail-open — any internal
error in the limiter must never block a legitimate request. For multi-replica deployments swap the
in-memory store for a shared one (Redis); that is the documented upgrade path.
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict, deque

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from vinchatbot.app.core.config import Settings

logger = logging.getLogger(__name__)

# Paths that must never be throttled (liveness probes, CORS preflight).
_EXEMPT_PATHS = frozenset({"/health"})


class SlidingWindowRateLimiter:
    """Per-key sliding-window counter. `check(key)` returns (allowed, retry_after_seconds)."""

    def __init__(self, max_requests: int, window_seconds: float) -> None:
        self.max_requests = max(1, int(max_requests))
        self.window = float(window_seconds)
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def check(self, key: str, now: float | None = None) -> tuple[bool, float]:
        now = time.monotonic() if now is None else now
        hits = self._hits[key]
        cutoff = now - self.window
        while hits and hits[0] <= cutoff:
            hits.popleft()
        if len(hits) >= self.max_requests:
            retry_after = self.window - (now - hits[0])
            return False, max(0.0, retry_after)
        hits.append(now)
        return True, 0.0

    def peek_blocked(self, key: str, now: float | None = None) -> tuple[bool, float]:
        """Is `key` over the limit RIGHT NOW, without recording a hit? Returns (blocked, retry_after).

        Use for login (check-before-verify): peek to reject, then `record` only on a FAILED attempt so
        successful logins are never throttled."""
        now = time.monotonic() if now is None else now
        hits = self._hits[key]
        cutoff = now - self.window
        while hits and hits[0] <= cutoff:
            hits.popleft()
        if len(hits) >= self.max_requests:
            return True, max(0.0, self.window - (now - hits[0]))
        return False, 0.0

    def record(self, key: str, now: float | None = None) -> None:
        """Record one hit for `key` (e.g. a failed login attempt)."""
        self._hits[key].append(time.monotonic() if now is None else now)

    def reset_key(self, key: str) -> None:
        """Clear all hits for `key` (e.g. on a successful login)."""
        self._hits.pop(key, None)


def _client_key(request: Request, trusted_proxies: frozenset[str] = frozenset()) -> str:
    """Best client identifier. Trust the first X-Forwarded-For hop ONLY when the socket peer is a
    known proxy (else a client could spoof XFF to dodge / poison the limit); otherwise the socket
    peer. Empty `trusted_proxies` → never trust XFF (safe default for direct exposure)."""
    peer = request.client.host if request.client else "unknown"
    if peer in trusted_proxies:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return peer


def _parse_trusted_proxies(raw: str | None) -> frozenset[str]:
    return frozenset(p.strip() for p in (raw or "").split(",") if p.strip())


def add_rate_limit_middleware(app: FastAPI, settings: Settings) -> None:
    """Register the rate-limit middleware on `app` when enabled. No-op when disabled."""
    if not settings.rate_limit_enabled:
        return

    limiter = SlidingWindowRateLimiter(
        settings.rate_limit_max_requests, settings.rate_limit_window_seconds
    )
    trusted_proxies = _parse_trusted_proxies(getattr(settings, "trusted_proxies", ""))

    @app.middleware("http")
    async def rate_limit_middleware(request: Request, call_next):
        if request.method == "OPTIONS" or request.url.path in _EXEMPT_PATHS:
            return await call_next(request)
        key = _client_key(request, trusted_proxies)
        try:
            allowed, retry_after = limiter.check(key)
        except Exception:  # fail-open: a limiter bug must not take down the API
            logger.debug("Rate limiter errored; allowing the request.", exc_info=True)
            return await call_next(request)
        if not allowed:
            retry_secs = int(retry_after) + 1
            logger.info(
                "Rate limit exceeded path=%s key=%s retry_after=%ds",
                request.url.path,
                key,
                retry_secs,
            )
            return JSONResponse(
                status_code=429,
                content={
                    "error": "rate_limited",
                    "detail": "Too many requests. Please slow down and try again shortly.",
                    "retry_after": retry_secs,
                },
                headers={"Retry-After": str(retry_secs)},
            )
        return await call_next(request)
