"""Context assembly helpers for retrieval results.

Currently: lost-in-the-middle reordering. Later phases add near-duplicate dedup and
indirect-injection scanning here (Track B/C).
"""

from __future__ import annotations

import dataclasses
import re
from collections.abc import Callable
from typing import Any, TypeVar

T = TypeVar("T")

_TERM_WORDS = ("fall", "spring", "summer")


def _rescore(item: Any, value: float) -> Any:
    """Return `item` with `score=value`. Uses dataclasses.replace for frozen dataclasses
    (e.g. RetrievedChunk), plain attribute assignment otherwise."""
    if dataclasses.is_dataclass(item) and not isinstance(item, type):
        return dataclasses.replace(item, score=value)
    item.score = value
    return item


def _retext(item: Any, text: str) -> Any:
    """Return `item` with `text=text` (frozen-dataclass safe; mirrors `_rescore`)."""
    if dataclasses.is_dataclass(item) and not isinstance(item, type):
        return dataclasses.replace(item, text=text)
    item.text = text
    return item


# A section sibling as returned by the fetch callback: (text, page_number, content_hash).
SectionSibling = tuple[str, int | None, str | None]


def _merge_section_text(
    anchor_text: str,
    siblings: list[SectionSibling],
    *,
    max_chars: int,
    max_siblings: int,
) -> str:
    """Stitch a section's chunks into one block: the matched (anchor) chunk first, then the
    remaining siblings in document order (page_number asc, None last), de-duplicated and
    bounded by `max_siblings` / `max_chars`."""
    anchor = (anchor_text or "").strip()
    ordered = sorted(
        ((index, (text or "").strip(), page) for index, (text, page, _hash) in enumerate(siblings)),
        key=lambda it: (it[2] is None, it[2] if it[2] is not None else 0, it[0]),
    )
    parts: list[str] = []
    seen: set[str] = set()

    def add(text: str) -> bool:
        norm = text.lower()
        if not text or norm in seen:
            return False
        seen.add(norm)
        parts.append(text)
        return True

    add(anchor)  # the matched chunk is always present and leads the merged block
    total = len(anchor)
    for _index, text, _page in ordered:
        if len(parts) >= max_siblings or not text or text.lower() in seen:
            if len(parts) >= max_siblings:
                break
            continue
        if total + len(text) > max_chars:
            break
        if add(text):
            total += len(text) + 2
    return "\n\n".join(parts) if parts else anchor


def expand_to_parent_sections(
    chunks: list[T],
    fetch_siblings: Callable[[str, str], list[SectionSibling]],
    *,
    max_chars: int,
    max_siblings: int,
    skip_subcategories: frozenset[str] = frozenset(),
) -> list[T]:
    """Parent-document retrieval: replace each fine chunk with the full text of the section
    it belongs to, so the LLM gets complete section context instead of an isolated fragment
    (the over-fragmentation fix). Chunks are matched/ranked small, then expanded large.

    Grouping key is `(parent_doc_id, section_id)`. `fetch_siblings(parent_doc_id, section_id)`
    returns every chunk in that section. Chunks lacking a `section_id` (no heading structure)
    pass through unchanged; when several top chunks share a section, they collapse to one
    (kept at the highest rank). Each merged chunk keeps the leading member's metadata + score.

    `skip_subcategories` opts whole subcategories out of expansion. Point-lookup tabular data
    (e.g. the calendar date grid) lists *similar-but-distinct* facts where adjacent rows are
    distractors, not context — stitching them makes the model over-share neighbouring values
    (a measured Phase 4 regression: a Fall add-deadline answer volunteered the course-drop
    date). Prose sections (policy/services) are where section context helps.
    """
    if not chunks:
        return chunks
    out: list[T] = []
    seen_sections: set[tuple[str, str]] = set()
    for chunk in chunks:
        md = getattr(chunk, "metadata", None)
        parent_id = getattr(md, "parent_doc_id", None)
        section_id = getattr(md, "section_id", None)
        subcategory = getattr(md, "subcategory", None)
        if not parent_id or not section_id or subcategory in skip_subcategories:
            out.append(chunk)
            continue
        key = (parent_id, section_id)
        if key in seen_sections:
            continue  # section already surfaced at a higher rank
        seen_sections.add(key)
        siblings = fetch_siblings(parent_id, section_id) or []
        merged = _merge_section_text(
            chunk.text, siblings, max_chars=max_chars, max_siblings=max_siblings
        )
        out.append(_retext(chunk, merged) if merged != chunk.text else chunk)
    return out


def apply_metadata_boosts(
    chunks: list[Any],
    query: str,
    hints: dict[str, Any] | None = None,
    enabled: bool = True,
) -> list[Any]:
    """Re-rank chunks (each having `.score` and `.metadata`) by adjusting the rerank score
    with metadata signals, then sorting. Boosts trusted sources and exact term/year/
    policy_code/category(hint) matches; penalizes low-trust external content.

    `hints` carries soft-routing category/subcategory from the calling specialist.
    """
    if not enabled or not chunks:
        return chunks
    hints = hints or {}
    q = query.lower()
    year = (re.search(r"20\d{2}", q) or [None])[0] if re.search(r"20\d{2}", q) else None
    query_terms = {t for t in _TERM_WORDS if t in q}

    rescored: list[Any] = []
    for chunk in chunks:
        if getattr(chunk, "score", None) is None:
            rescored.append(chunk)
            continue
        md = chunk.metadata
        factor = 1.0
        trust = getattr(md, "source_trust", None)
        if trust == "official_high":
            factor *= 1.15
        elif trust == "external_low":
            factor *= 0.7
        if hints.get("category") and getattr(md, "category", None) == hints["category"]:
            factor *= 1.1
        if hints.get("subcategory") and getattr(md, "subcategory", None) == hints["subcategory"]:
            factor *= 1.1
        if year and (getattr(md, "academic_year", None) or "") and year in md.academic_year:
            factor *= 1.1
        if query_terms and getattr(md, "term", None) and any(t in md.term.lower() for t in query_terms):
            factor *= 1.1
        code = getattr(md, "policy_code", None)
        if code and code.lower() in q:
            factor *= 1.3
        rescored.append(_rescore(chunk, chunk.score * factor))

    return sorted(rescored, key=lambda c: (c.score if getattr(c, "score", None) is not None else -1.0), reverse=True)


def _word_set(text: str) -> set[str]:
    return {tok for tok in text.lower().split() if tok}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def dedup_by_text(items: list[T], text_of: Callable[[T], str], threshold: float = 0.9) -> list[T]:
    """Drop near-duplicate items, keeping the first (highest-ranked) occurrence.

    Near-duplicate = word-set Jaccard >= threshold. Used so a policy's HTML and PDF copies
    (near-identical text) don't both crowd the retrieved context.
    """
    kept: list[T] = []
    kept_shingles: list[set[str]] = []
    for item in items:
        shingles = _word_set(text_of(item))
        if any(_jaccard(shingles, prev) >= threshold for prev in kept_shingles):
            continue
        kept.append(item)
        kept_shingles.append(shingles)
    return kept


def select_dynamic_k(
    items: list[T],
    score_of: Callable[[T], float | None],
    *,
    enabled: bool,
    min_k: int,
    max_k: int,
    ratio: float,
) -> list[T]:
    """Pick a variable number of top results from a relevance-descending list.

    Keep items whose score is >= ratio * top_score, bounded by [min_k, max_k]. When
    disabled or scores are missing, fall back to the top max_k.
    """
    if not items:
        return []
    top = score_of(items[0])
    if not enabled or top is None:
        return items[:max_k]
    kept = [item for item in items if (score_of(item) or 0.0) >= ratio * top][:max_k]
    if len(kept) < min_k:
        kept = items[:min_k]
    return kept


def reorder_for_long_context(items: list[T]) -> list[T]:
    """Mitigate "lost in the middle": given items sorted by *descending* relevance,
    return a new ordering with the most-relevant items at BOTH ends and the least-relevant
    in the middle (the LangChain LongContextReorder pattern).

    Example: [a,b,c,d,e] (a best) -> [a,c,e,d,b] (a first, b last, e buried in the middle).
    """
    if len(items) <= 2:
        return list(items)
    ascending = list(reversed(items))  # least-relevant first
    reordered: list[T] = []
    for index, item in enumerate(ascending):
        if index % 2 == 1:
            reordered.append(item)
        else:
            reordered.insert(0, item)
    return reordered
