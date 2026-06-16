"""Input engineering for retrieval: multi-query expansion + reciprocal rank fusion.

`expand_query` produces a few paraphrase/synonym variants of the user's question (same
language) via a cheap LLM, with a safe fallback to the original query. `reciprocal_rank_fusion`
fuses the per-variant ranked result lists.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from typing import TypeVar

from vinchatbot.app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)

T = TypeVar("T")

# Point-lookup detection (Phase 1.7 adaptive routing). A query is a point-lookup when its routed
# domain is calendar/financial, or it names a specific year/term/amount/currency or a lookup keyword
# (EN + VI, accented and accent-less). These are the queries whose answer is one exact row among
# near-identical neighbours, where multi-query expansion + rerank surfaces an adjacent wrong value.
_POINTLOOKUP_CATS = {"calendar", "financial"}
_POINTLOOKUP_RE = re.compile(
    r"20\d{2}|\b(fall|spring|summer)\b|\bvnd\b|₫|\d[\d.,]{4,}\d"
    r"|deadline|tuition|\bfee\b|fine|scholarship|convocation"
    r"|học phí|hoc phi|lệ phí|le phi|học bổng|hoc bong|hạn nộp|han nop|lịch thi|lich thi|học kỳ|hoc ky",
    re.IGNORECASE,
)


def is_point_lookup(query: str, category: str | None = None) -> bool:
    """True for exact-value lookups (dates/amounts/codes) that should bypass query expansion and
    read the full section instead of trusting the reranker's top chunk. `category` is the routed
    sub-category/category hint (e.g. 'calendar', 'financial')."""
    if category and category.strip().lower() in _POINTLOOKUP_CATS:
        return True
    return bool(_POINTLOOKUP_RE.search(query or ""))

# Query expansion has two independent kinds (Phase 1.8 made them orthogonal):
#  • paraphrase  — same-language synonym/keyword variants (multi-query recall). Gated by
#    ENABLE_QUERY_EXPANSION; off for calendar point-lookups (date-grid neighbours are distractors).
#  • cross_lingual — ONE VI↔EN translation of the query, so a question in one language still matches
#    sources written in the other (e.g. VI query vs the English fee tariff / calendar). Gated by
#    ENABLE_CROSSLINGUAL_EXPANSION; applies on every domain.
_PARAPHRASE_SYSTEM = (
    "You expand a student's search query for a VinUni academic assistant. Produce "
    "{n} alternative search queries that paraphrase or add synonyms/keywords for the same "
    "intent, IN THE SAME LANGUAGE as the input. Output only the queries, one per line, no "
    "numbering, no commentary."
)
_PARAPHRASE_XLING_SYSTEM = (
    "You expand a student's search query for a VinUni academic assistant. Produce {n} alternative "
    "search queries for the SAME intent: paraphrases/synonyms in the same language as the input, AND "
    "one accurate translation of the query into the OTHER language (Vietnamese↔English), so it can "
    "match sources written in either language. Output only the queries, one per line, no numbering."
)
_XLING_ONLY_SYSTEM = (
    "Translate this VinUni student's search query into the OTHER language (Vietnamese→English or "
    "English→Vietnamese), preserving the exact intent and any names, dates and amounts. Output ONLY "
    "the single translated query — no original, no commentary."
)


async def expand_query(
    query: str,
    settings: Settings | None = None,
    model=None,
    max_variants: int = 2,
    paraphrase: bool = True,
    cross_lingual: bool = False,
) -> list[str]:
    """Return ``[original, ...variants]`` in one LLM call.

    `paraphrase` adds up to `max_variants` same-language paraphrases; `cross_lingual` adds one VI↔EN
    translation. Any combination is valid; with neither (or no API key / error) returns ``[query]``.
    The caller (tools._search) decides the flags from settings + routed domain.
    """

    settings = settings or get_settings()
    if not settings.openrouter_api_key or max_variants <= 0:
        return [query]
    if not paraphrase and not cross_lingual:
        return [query]

    if paraphrase and cross_lingual:
        system, cap = _PARAPHRASE_XLING_SYSTEM.format(n=max_variants), max_variants + 2
    elif cross_lingual:
        system, cap = _XLING_ONLY_SYSTEM, 2
    else:
        system, cap = _PARAPHRASE_SYSTEM.format(n=max_variants), max_variants + 1

    try:
        if model is None:
            from vinchatbot.app.llm.openrouter_chat import build_chat_model

            model = build_chat_model(settings)
        response = await model.ainvoke(
            [
                {"role": "system", "content": system},
                {"role": "user", "content": query},
            ]
        )
        content = response.content if isinstance(response.content, str) else str(response.content)
        variants: list[str] = [query]
        for line in content.splitlines():
            cleaned = line.strip().lstrip("-•*0123456789. )").strip()
            if cleaned and cleaned.lower() != query.lower() and cleaned not in variants:
                variants.append(cleaned)
        return variants[:cap]
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
