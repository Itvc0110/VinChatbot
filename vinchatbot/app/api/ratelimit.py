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


def _client_key(request: Request) -> str:
    """Best client identifier: first X-Forwarded-For hop (behind a proxy) else the socket peer."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def add_rate_limit_middleware(app: FastAPI, settings: Settings) -> None:
    """Register the rate-limit middleware on `app` when enabled. No-op when disabled."""
    if not settings.rate_limit_enabled:
        return

    limiter = SlidingWindowRateLimiter(
        settings.rate_limit_max_requests, settings.rate_limit_window_seconds
    )

    @app.middleware("http")
    async def rate_limit_middleware(request: Request, call_next):
        if request.method == "OPTIONS" or request.url.path in _EXEMPT_PATHS:
            return await call_next(request)
        try:
            allowed, retry_after = limiter.check(_client_key(request))
        except Exception:  # fail-open: a limiter bug must not take down the API
            logger.debug("Rate limiter errored; allowing the request.", exc_info=True)
            return await call_next(request)
        if not allowed:
            retry_secs = int(retry_after) + 1
            logger.info(
                "Rate limit exceeded path=%s key=%s retry_after=%ds",
                request.url.path,
                _client_key(request),
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
