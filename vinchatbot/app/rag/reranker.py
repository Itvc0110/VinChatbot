from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass

import httpx

from vinchatbot.app.core.cache import redis_get, redis_set
from vinchatbot.app.core.config import Settings, get_settings
from vinchatbot.app.core.observability import incr_rerank_count, record_stage, rerank_cost_usd

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RerankResult:
    index: int
    score: float


class OpenRouterReranker:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def _cache_payload(self, query: str, documents: list[str], top_n: int) -> str:
        return json.dumps(
            [self.settings.openrouter_rerank_model, query, documents, top_n], ensure_ascii=False
        )

    async def rerank(self, query: str, documents: list[str], top_n: int = 8) -> list[RerankResult]:
        if not documents:
            return []
        # Mass cache (A2c): exact-match cache keyed on (model, query, documents, top_n). A HIT returns the
        # same scores (reproducible — freezes the hosted reranker's float jitter) and costs nothing (no
        # cohere call → not counted in the ledger). Fail-open. Checked BEFORE incr_rerank_count.
        cache_payload = self._cache_payload(query, documents, top_n) if self.settings.enable_rerank_cache else None
        if cache_payload is not None:
            cached = redis_get("rerank", cache_payload, self.settings)
            if cached is not None:
                try:
                    return [RerankResult(index=int(d["index"]), score=float(d["score"])) for d in json.loads(cached)]
                except Exception:
                    pass  # corrupt entry → fall through to a live rerank
        if not self.settings.openrouter_api_key:
            logger.warning("OPENROUTER_API_KEY is missing; returning original retrieval order.")
            return [RerankResult(index=index, score=1.0 / (index + 1)) for index in range(len(documents))]

        headers = {
            "Authorization": f"Bearer {self.settings.openrouter_api_key}",
            "Content-Type": "application/json",
        }
        incr_rerank_count()  # one billed Cohere "search" — counted per turn for the cost log
        started = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.settings.openrouter_base_url.rstrip('/')}/rerank",
                    headers=headers,
                    json={
                        "model": self.settings.openrouter_rerank_model,
                        "query": query,
                        "documents": documents,
                        "top_n": min(top_n, len(documents)),
                    },
                )
                response.raise_for_status()
                payload = response.json()
        except Exception:
            # Reranking is a precision boost, not a hard dependency. On any failure
            # (bad model id, network, rate limit) fall back to the original retrieval
            # order rather than failing the whole chat turn.
            record_stage(
                "rerank",
                latency_ms=(time.perf_counter() - started) * 1000,
                est_cost_usd=rerank_cost_usd(self.settings.openrouter_rerank_model),
            )
            logger.warning("Rerank call failed; falling back to original retrieval order.", exc_info=True)
            return []
        record_stage(
            "rerank",
            latency_ms=(time.perf_counter() - started) * 1000,
            est_cost_usd=rerank_cost_usd(self.settings.openrouter_rerank_model),
        )

        results = []
        for item in payload.get("results", []):
            results.append(
                RerankResult(
                    index=int(item["index"]),
                    score=float(item.get("relevance_score", 0.0)),
                )
            )
        if cache_payload is not None and results:
            redis_set(
                "rerank",
                cache_payload,
                json.dumps([{"index": r.index, "score": r.score} for r in results], ensure_ascii=False),
                self.settings,
            )
        return results

