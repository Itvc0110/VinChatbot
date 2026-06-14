"""Input engineering for retrieval: multi-query expansion + reciprocal rank fusion.

`expand_query` produces a few paraphrase/synonym variants of the user's question (same
language) via a cheap LLM, with a safe fallback to the original query. `reciprocal_rank_fusion`
fuses the per-variant ranked result lists.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TypeVar

from vinchatbot.app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)

T = TypeVar("T")

_EXPANSION_SYSTEM = (
    "You expand a student's search query for a VinUni academic assistant. Produce "
    "{n} alternative search queries that paraphrase or add synonyms/keywords for the same "
    "intent, IN THE SAME LANGUAGE as the input. Output only the queries, one per line, no "
    "numbering, no commentary."
)


async def expand_query(
    query: str,
    settings: Settings | None = None,
    model=None,
    max_variants: int = 2,
) -> list[str]:
    """Return [original, ...up to max_variants paraphrases]. Falls back to [query]."""

    settings = settings or get_settings()
    if not settings.enable_query_expansion or not settings.openrouter_api_key or max_variants <= 0:
        return [query]
    try:
        if model is None:
            from vinchatbot.app.llm.openrouter_chat import build_chat_model

            model = build_chat_model(settings)
        response = await model.ainvoke(
            [
                {"role": "system", "content": _EXPANSION_SYSTEM.format(n=max_variants)},
                {"role": "user", "content": query},
            ]
        )
        content = response.content if isinstance(response.content, str) else str(response.content)
        variants: list[str] = [query]
        for line in content.splitlines():
            cleaned = line.strip().lstrip("-•*0123456789. )").strip()
            if cleaned and cleaned.lower() != query.lower() and cleaned not in variants:
                variants.append(cleaned)
        return variants[: max_variants + 1]
    except Exception:
        logger.debug("Query expansion failed; using the original query only.", exc_info=True)
        return [query]


def reciprocal_rank_fusion(
    ranked_lists: list[list[T]],
    key: Callable[[T], str],
    k: int = 60,
) -> list[T]:
    """Fuse multiple relevance-descending lists into one via Reciprocal Rank Fusion."""

    scores: dict[str, float] = {}
    items: dict[str, T] = {}
    for ranked in ranked_lists:
        for rank, item in enumerate(ranked):
            identifier = key(item)
            scores[identifier] = scores.get(identifier, 0.0) + 1.0 / (k + rank + 1)
            items.setdefault(identifier, item)
    ordered_ids = sorted(scores, key=lambda identifier: scores[identifier], reverse=True)
    return [items[identifier] for identifier in ordered_ids]
