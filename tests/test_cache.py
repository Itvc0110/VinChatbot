from __future__ import annotations

from types import SimpleNamespace

import vinchatbot.app.core.cache as cache_mod
from vinchatbot.app.core.cache import RedisLLMCache, redis_get, redis_set


class _FakeRedis:
    def __init__(self) -> None:
        self.store: dict[str, str] = {}

    def get(self, key):
        return self.store.get(key)

    def set(self, key, value, ex=None):
        self.store[key] = value

    def ping(self):
        return True


def _settings(version: str = "v1", ttl: int = 0) -> SimpleNamespace:
    return SimpleNamespace(
        redis_url="redis://x", enable_llm_cache=True, enable_rerank_cache=True,
        cache_version=version, cache_ttl_seconds=ttl,
    )


def test_fail_open_without_redis_url():
    # No REDIS_URL → client is None → get returns None, set is a no-op (never raises).
    s = _settings()
    s.redis_url = None
    assert redis_get("llm", "p", s) is None
    redis_set("llm", "p", "v", s)  # must not raise


def test_roundtrip_and_version_namespacing(monkeypatch):
    fake = _FakeRedis()
    monkeypatch.setattr(cache_mod, "_client", lambda settings: fake)
    s = _settings()
    assert redis_get("rerank", "payloadA", s) is None  # miss
    redis_set("rerank", "payloadA", "[1,2]", s)
    assert redis_get("rerank", "payloadA", s) == "[1,2]"  # hit
    # different payload / namespace → different key → miss
    assert redis_get("rerank", "payloadB", s) is None
    assert redis_get("llm", "payloadA", s) is None
    # CACHE_VERSION bump invalidates (namespacing)
    assert redis_get("rerank", "payloadA", _settings(version="v2")) is None


def test_fail_open_on_redis_error(monkeypatch):
    class _Boom:
        def get(self, key):
            raise RuntimeError("boom")

        def set(self, key, value, ex=None):
            raise RuntimeError("boom")

    monkeypatch.setattr(cache_mod, "_client", lambda settings: _Boom())
    s = _settings()
    assert redis_get("llm", "p", s) is None  # error → miss
    redis_set("llm", "p", "v", s)  # error → swallowed


def test_redis_llm_cache_roundtrip(monkeypatch):
    from langchain_core.outputs import Generation

    fake = _FakeRedis()
    monkeypatch.setattr(cache_mod, "_client", lambda settings: fake)
    cache = RedisLLMCache(_settings())
    assert cache.lookup("prompt", "llm_string") is None  # miss
    cache.update("prompt", "llm_string", [Generation(text="cached answer")])
    got = cache.lookup("prompt", "llm_string")
    assert got and got[0].text == "cached answer"  # exact-match hit, round-tripped
    assert cache.lookup("OTHER prompt", "llm_string") is None  # different prompt → miss (A/B-safe)
