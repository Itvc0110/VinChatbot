from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from vinchatbot.app.api.ratelimit import SlidingWindowRateLimiter, add_rate_limit_middleware


def test_sliding_window_allows_then_blocks_then_recovers():
    rl = SlidingWindowRateLimiter(max_requests=2, window_seconds=60)
    assert rl.check("k", now=0.0)[0] is True
    assert rl.check("k", now=1.0)[0] is True
    allowed, retry_after = rl.check("k", now=2.0)
    assert allowed is False
    assert retry_after > 0  # ~58s until the oldest hit (t=0) leaves the window
    # Once the window has slid past the first two hits, the key is allowed again.
    assert rl.check("k", now=61.0)[0] is True


def test_sliding_window_keys_are_independent():
    rl = SlidingWindowRateLimiter(max_requests=1, window_seconds=60)
    assert rl.check("a", now=0.0)[0] is True
    assert rl.check("a", now=1.0)[0] is False
    assert rl.check("b", now=1.0)[0] is True  # different key, own budget


def _build_app(**settings_overrides) -> FastAPI:
    base = {"rate_limit_enabled": True, "rate_limit_max_requests": 2, "rate_limit_window_seconds": 60}
    base.update(settings_overrides)
    app = FastAPI()
    add_rate_limit_middleware(app, SimpleNamespace(**base))

    @app.get("/ping")
    async def ping():
        return {"ok": True}

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    return app


def test_middleware_returns_429_after_limit():
    client = TestClient(_build_app())
    assert client.get("/ping").status_code == 200
    assert client.get("/ping").status_code == 200
    resp = client.get("/ping")
    assert resp.status_code == 429
    assert resp.headers.get("Retry-After")
    body = resp.json()
    assert body["error"] == "rate_limited"
    assert body["retry_after"] >= 1


def test_health_is_exempt():
    client = TestClient(_build_app(rate_limit_max_requests=1))
    for _ in range(5):
        assert client.get("/health").status_code == 200


def test_disabled_is_passthrough():
    client = TestClient(_build_app(rate_limit_enabled=False, rate_limit_max_requests=1))
    for _ in range(5):
        assert client.get("/ping").status_code == 200
