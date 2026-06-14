from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx

from vinchatbot.app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RerankResult:
    index: int
    score: float


class OpenRouterReranker:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    async def rerank(self, query: str, documents: list[str], top_n: int = 8) -> list[RerankResult]:
        if not documents:
            return []
        if not self.settings.openrouter_api_key:
            logger.warning("OPENROUTER_API_KEY is missing; returning original retrieval order.")
            return [RerankResult(index=index, score=1.0 / (index + 1)) for index in range(len(documents))]

        headers = {
            "Authorization": f"Bearer {self.settings.openrouter_api_key}",
            "Content-Type": "application/json",
        }
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
            logger.warning("Rerank call failed; falling back to original retrieval order.", exc_info=True)
            return []

        results = []
        for item in payload.get("results", []):
            results.append(
                RerankResult(
                    index=int(item["index"]),
                    score=float(item.get("relevance_score", 0.0)),
                )
            )
        return results

