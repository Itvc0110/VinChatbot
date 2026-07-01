"""Deterministic override catalog for the Form Assistant.

WHY THIS EXISTS: official form files (PDF/DOCX) are mostly blank fields, so they embed weakly and rank below
the forms-hub page in vector search — a query like "đơn xin nghỉ học" surfaces the hub, not the exact
Defer/Withdraw file. This module is a small, curated, deterministic keyword→file lookup consulted by
`search_forms` so the highest-traffic forms are cited by their EXACT official URL. It is an OVERRIDE layer
only: RAG still covers everything not listed in `data/forms_catalog.json`.

DRAWBACKS (deliberately bounded): the catalog can go stale if the registrar re-versions a form. Mitigations —
(1) it only lists the ~8 stable core forms; (2) a stale/removed URL simply falls back to the RAG path; (3) the
JSON records provenance + a `verified_on` date; (4) the loader is **fail-open** (any read/parse error → empty
catalog, search still works). Matching is accent-folded so no-diacritics queries ("nghi hoc") still hit.
"""

from __future__ import annotations

import json
import logging
import unicodedata
from functools import lru_cache
from pathlib import Path

from vinchatbot.app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)

# vinchatbot/app/rag/forms_catalog.py → parents[3] == repo root (holds data/).
_REPO_ROOT = Path(__file__).resolve().parents[3]


def _fold(text: str) -> str:
    """Lowercase, map Vietnamese đ→d, and strip diacritics so 'Nghỉ học' == 'nghi hoc'."""
    lowered = (text or "").lower().replace("đ", "d")
    decomposed = unicodedata.normalize("NFD", lowered)
    return "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")


@lru_cache(maxsize=4)
def _load(path_str: str) -> tuple[dict, ...]:
    """Load + validate the catalog once per path. Fail-open to () on any error."""
    path = Path(path_str)
    try:
        with path.open(encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError, ValueError):
        logger.warning("Forms catalog not loaded from %s; falling back to RAG only.", path_str, exc_info=True)
        return ()
    forms = data.get("forms") if isinstance(data, dict) else None
    if not isinstance(forms, list):
        return ()
    valid: list[dict] = []
    for form in forms:
        if isinstance(form, dict) and form.get("url") and form.get("keywords"):
            valid.append(form)
    return tuple(valid)


def _catalog_path(settings: Settings) -> str:
    path = Path(settings.forms_catalog_path)
    if not path.is_absolute():
        path = _REPO_ROOT / path
    return str(path)


def load_forms_catalog(settings: Settings | None = None) -> tuple[dict, ...]:
    settings = settings or get_settings()
    return _load(_catalog_path(settings))


def match_forms(query: str, settings: Settings | None = None, limit: int = 4) -> list[dict]:
    """Return catalog forms whose keywords appear in `query`, best-match first.

    Each result: {id, title, url, department}. Empty when nothing matches or the catalog is unavailable
    (→ `search_forms` just uses its RAG-extracted form links).
    """
    forms = load_forms_catalog(settings)
    if not query or not forms:
        return []
    folded_query = _fold(query)
    scored: list[tuple[int, int, dict]] = []
    for index, form in enumerate(forms):
        hits = sum(1 for kw in form.get("keywords", []) if kw and _fold(kw) in folded_query)
        if hits:
            title = form.get("name_vi") or form.get("name_en") or form.get("id") or ""
            scored.append(
                (
                    hits,
                    index,
                    {
                        "id": form.get("id"),
                        "title": title,
                        "url": form["url"],
                        "department": form.get("department"),
                    },
                )
            )
    # Best match first (more keyword hits), ties keep catalog order (curated priority).
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [entry for _hits, _index, entry in scored[:limit]]
