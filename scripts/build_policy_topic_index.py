"""Build the ingest-time policy topic index (Phase 1.24) — the generality fix for the doc-pin.

Scans every canonical policy page (`policy_html` / `financial_policy`) in the Qdrant collection and emits, per
page, the salient terms of its `document_title`. `policy_lookup.match()` uses this as a fallback AFTER the
hand-curated `POLICY_TOPICS`: a query that matches no curated keyword is pinned to the canonical page whose
title it overlaps best (single-winner; ties → fail-open). This extends coverage from the 17 curated policies
to all ~155 canonical pages (and any future staff upload, once re-run) WITHOUT touching the curated map.

Mirrors `scripts/build_structured_index.py`: a small compact JSON artifact regenerated after each ingest.
Output: <PROCESSED_DATA_DIR>/policy_topic_index.json = {source_url: [salient title terms]}.
Read-only on Qdrant (metadata scroll, no vectors). Usage: `python scripts/build_policy_topic_index.py`.
"""

from __future__ import annotations

import json
from pathlib import Path

from qdrant_client import QdrantClient
from qdrant_client.models import FieldCondition, Filter, MatchAny

from vinchatbot.app.core.config import get_settings
from vinchatbot.app.rag.context import _salient_terms
from vinchatbot.app.storage.qdrant_store import qdrant_location_kwargs

CANONICAL_TYPES = ["policy_html", "financial_policy"]


def build_index() -> dict[str, list[str]]:
    settings = get_settings()
    client = QdrantClient(**qdrant_location_kwargs(settings))
    flt = Filter(must=[FieldCondition(key="metadata.document_type", match=MatchAny(any=CANONICAL_TYPES))])
    index: dict[str, list[str]] = {}
    offset = None
    try:
        while True:
            points, offset = client.scroll(
                collection_name=settings.qdrant_collection, scroll_filter=flt,
                with_payload=True, with_vectors=False, limit=500, offset=offset,
            )
            for point in points:
                md = (point.payload or {}).get("metadata", {}) or {}
                url = md.get("source_url") or ""
                title = md.get("document_title") or ""
                if not url or url in index:
                    continue
                terms = sorted(_salient_terms(title))
                if terms:  # skip pages whose title is all stopwords / empty
                    index[url] = terms
            if offset is None:
                break
    finally:
        client.close()
    return index


def main() -> None:
    settings = get_settings()
    index = build_index()
    out = Path(settings.processed_data_dir) / "policy_topic_index.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(index, ensure_ascii=False, indent=0), encoding="utf-8")
    print(f"policy_topic_index: {len(index)} canonical pages -> {out}")


if __name__ == "__main__":
    main()
