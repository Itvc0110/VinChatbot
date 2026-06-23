"""Mass cache (Phase A2c) — exact-match Redis cache of LLM responses + rerank scores.

Keyed on the FULL prompt/content so it is reproducible (same input → same output → kills run-to-run LLM
noise) AND A/B-safe (a config change alters the prompt/docs → different key → recompute, never masked).
Namespaced by `CACHE_VERSION` for logic-only invalidation. **Fail-open by construction:** no `REDIS_URL`,
an unreachable server, or any redis error is treated as a cache MISS — never an exception — so correctness
is never at risk and the pipeline runs exactly as if uncached.
"""

from __future__ import annotations

import hashlib
import logging

from langchain_core.caches import BaseCache
from langchain_core.load import dumps, loads

from vinchatbot.app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)

_CLIENT_CACHE: dict[str, object] = {}  # redis_url -> client | None (None = unavailable, don't retry per url)
_LLM_CACHE_INSTALLED = False


def _client(settings: Settings):
    """Process-cached redis client for `settings.redis_url`, or None (fail-open)."""
    url = settings.redis_url
    if not url:
        return None
    if url in _CLIENT_CACHE:
        return _CLIENT_CACHE[url]
    client = None
    try:
        import redis

        client = redis.from_url(url, socket_connect_timeout=5, socket_timeout=5, decode_responses=True)
        client.ping()
    except Exception:
        logger.warning("Redis cache unavailable; running fail-open (uncached).", exc_info=True)
        client = None
    _CLIENT_CACHE[url] = client
    return client


def _key(settings: Settings, namespace: str, payload: str) -> str:
    digest = hashlib.blake2b(payload.encode("utf-8"), digest_size=16).hexdigest()
    return f"{settings.cache_version}:{namespace}:{digest}"


def redis_get(namespace: str, payload: str, settings: Settings | None = None) -> str | None:
    settings = settings or get_settings()
    client = _client(settings)
    if client is None:
        return None
    try:
        return client.get(_key(settings, namespace, payload))
    except Exception:
        return None


def redis_set(namespace: str, payload: str, value: str, settings: Settings | None = None) -> None:
    settings = settings or get_settings()
    client = _client(settings)
    if client is None:
        return
    try:
        ttl = settings.cache_ttl_seconds
        key = _key(settings, namespace, payload)
        if ttl and ttl > 0:
            client.set(key, value, ex=ttl)
        else:
            client.set(key, value)
    except Exception:
        return


def install_llm_cache(settings: Settings | None = None) -> bool:
    """Install the global LangChain LLM cache (idempotent). Returns True if active. Gated on
    `enable_llm_cache` + a reachable `redis_url`; fail-open otherwise. Called lazily from build_chat_model
    so BOTH the API server and the eval/script paths get it."""
    global _LLM_CACHE_INSTALLED
    if _LLM_CACHE_INSTALLED:
        return True
    settings = settings or get_settings()
    if not settings.enable_llm_cache or _client(settings) is None:
        return False
    try:
        from langchain_core.globals import set_llm_cache

        set_llm_cache(RedisLLMCache(settings))
        _LLM_CACHE_INSTALLED = True
        logger.info("LLM response cache installed (exact-match Redis, version=%s).", settings.cache_version)
        return True
    except Exception:
        logger.warning("Could not install LLM cache; running fail-open (uncached).", exc_info=True)
        return False


class RedisLLMCache(BaseCache):
    """LangChain global LLM cache backed by exact-match Redis. Keys on (prompt, llm_string) — llm_string
    captures the model + params, the prompt captures the full messages (incl. retrieved context) → A/B-safe.
    Values are LangChain-serialized generations (`dumps`/`loads`). Every op is fail-open (a redis/serde
    error → cache MISS, which LangChain then recomputes)."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def lookup(self, prompt: str, llm_string: str):
        raw = redis_get("llm", f"{prompt}\x00{llm_string}", self.settings)
        if raw is None:
            return None
        try:
            return loads(raw)
        except Exception:
            return None

    def update(self, prompt: str, llm_string: str, return_val) -> None:
        try:
            redis_set("llm", f"{prompt}\x00{llm_string}", dumps(return_val), self.settings)
        except Exception:
            return

    def clear(self, **kwargs) -> None:  # noqa: ARG002 - BaseCache interface
        return
