"""Input engineering for retrieval: multi-query expansion + reciprocal rank fusion.

`expand_query` produces a few paraphrase/synonym variants of the user's question (same
language) via a cheap LLM, with a safe fallback to the original query. `reciprocal_rank_fusion`
fuses the per-variant ranked result lists.
"""

from __future__ import annotations

import logging
import re
import time
from collections.abc import Callable
from typing import TypeVar

from vinchatbot.app.core.config import Settings, get_settings
from vinchatbot.app.core.observability import record_llm_usage

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


# List-lookup detection (Phase 1.27/A6). The mirror of point-lookup: a question asking for MULTIPLE rows
# ("all/each/every program", "compare … across", "list … for both terms"). These need a WIDER context +
# enumeration, the opposite of the point-lookup narrowing. Deliberately list-SPECIFIC markers only — VI
# quantifiers that double as RATE words are EXCLUDED so they don't misfire: "các" (the/plural), and crucially
# "mỗi"/"từng"/"mọi" (each/every — but "mỗi ngày" = per day, "mỗi tín chỉ" = per credit are RATES, not lists;
# "mỗi ngày" was wrongly hijacking the library-fine question into the tuition matrix). The unambiguous VI list
# words remain (tất cả/liệt kê/so sánh/toàn bộ); EN "each/every" stay (EN rates use "per", not each/every).
_LISTLOOKUP_RE = re.compile(
    r"\b(all|each|every|both|list|compare|across)\b"
    r"|tất cả|tat ca|so sánh|so sanh|liệt kê|liet ke|toàn bộ|toan bo",
    re.IGNORECASE,
)


def is_list_lookup(query: str, category: str | None = None) -> bool:
    """True for multi-row 'list' questions that should WIDEN retrieval + enumerate every matching row,
    rather than narrow to one value (Phase 1.27/A6). Query-driven only (category unused) so it stays
    domain-agnostic; conservative markers so it does not fire on single-target point-lookups."""
    return bool(_LISTLOOKUP_RE.search(query or ""))


# Deterministic month+year date normalization (Phase 1.12). The reported failure: "events for 6/2026"
# worked but "tháng 6 năm 2026" (VI) did not — same date, different surface form. These regexes detect a
# (month, year) in any of the common VI/EN/numeric forms and emit the OTHER canonical forms, so a date
# query matches the corpus regardless of phrasing. Pure regex → deterministic (no LLM, no consistency
# cost), and additive to the multi-query set.
_EN_MONTHS = (
    "january", "february", "march", "april", "may", "june",
    "july", "august", "september", "october", "november", "december",
)
_EN_MONTH_TO_NUM = {name: i + 1 for i, name in enumerate(_EN_MONTHS)}
_EN_MONTH_TO_NUM.update({name[:3]: i + 1 for i, name in enumerate(_EN_MONTHS)})  # jan, feb, ...
_DATE_RE_VI = re.compile(r"tháng\s*(\d{1,2})\s*(?:năm\s*)?/?\s*(20\d{2})", re.IGNORECASE)
_DATE_RE_NUM = re.compile(r"\b(\d{1,2})\s*/\s*(20\d{2})\b")
_DATE_RE_EN = re.compile(r"\b([A-Za-z]{3,9})\.?\s+(20\d{2})\b")


def extract_month_years(query: str) -> list[tuple[int, int]]:
    """Return the unique (month, year) pairs named in `query`, in VI/EN/numeric forms (sorted).
    Shared by `normalize_date_phrases` (query expansion) and the calendar metadata boost (year
    disambiguation)."""
    q = query or ""
    found: set[tuple[int, int]] = set()
    for pat in (_DATE_RE_VI, _DATE_RE_NUM):
        for m in pat.finditer(q):
            month, year = int(m.group(1)), int(m.group(2))
            if 1 <= month <= 12:
                found.add((month, year))
    for m in _DATE_RE_EN.finditer(q):
        month = _EN_MONTH_TO_NUM.get(m.group(1).lower())
        if month:
            found.add((month, int(m.group(2))))
    return sorted(found)


def normalize_date_phrases(query: str) -> list[str]:
    """Return extra both-language canonical forms of any month+year in `query` (deduped, excluding
    forms already present). E.g. '6/2026' -> ['tháng 6 năm 2026', 'June 2026', '06/2026']."""
    lowered = (query or "").lower()
    variants: list[str] = []
    for month, year in extract_month_years(query):
        for cand in (
            f"tháng {month} năm {year}",
            f"{_EN_MONTHS[month - 1].capitalize()} {year}",
            f"{month}/{year}",
            f"{month:02d}/{year}",
        ):
            if cand.lower() not in lowered and cand not in variants:
                variants.append(cand)
    return variants

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

            # temp=0: deterministic variants → stable candidate pool → stable retrieval (Phase 1.11).
            model = build_chat_model(settings, temperature=0.0)
        started = time.perf_counter()
        response = await model.ainvoke(
            [
                {"role": "system", "content": system},
                {"role": "user", "content": query},
            ]
        )
        record_llm_usage(
            "query_expansion",
            settings.openrouter_chat_model,
            response,
            (time.perf_counter() - started) * 1000,
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
