"""Qdrant collection inventory (data-integrity check).

The ingest pipeline never globally clears the collection — it upserts by deterministic id and deletes
old chunks only for parent_doc_ids present in the current run. So stale points from past ingests can
accumulate. This script reports what's actually live: total points, distinct sources + per-source
counts, calendar academic-year spread, and exact-duplicate text (a sign of chunk_id churn across
ingest versions).

Usage: py scripts/qdrant_inventory.py
"""

from __future__ import annotations

import hashlib
from collections import Counter

from vinchatbot.app.core.config import get_settings
from vinchatbot.app.storage.qdrant_store import qdrant_location_kwargs


def main() -> None:
    from qdrant_client import QdrantClient

    settings = get_settings()
    coll = settings.qdrant_collection
    client = QdrantClient(**qdrant_location_kwargs(settings))

    info = client.get_collection(coll)
    print(f"collection: {coll}")
    print(f"reported points_count: {info.points_count}")

    sources: Counter[str] = Counter()
    subcats: Counter[str] = Counter()
    cal_years: Counter[str] = Counter()
    text_hashes: Counter[str] = Counter()
    total = 0
    offset = None
    while True:
        points, offset = client.scroll(
            collection_name=coll, with_payload=True, with_vectors=False, limit=500, offset=offset
        )
        for p in points:
            payload = p.payload or {}
            md = payload.get("metadata", {}) or {}
            total += 1
            sources[md.get("source_url") or "(none)"] += 1
            subcats[md.get("subcategory") or md.get("category") or "(none)"] += 1
            if md.get("category") == "academic" or md.get("subcategory") == "calendar":
                cal_years[str(md.get("academic_year") or "(none)")] += 1
            text = payload.get("page_content") or ""
            if text:
                text_hashes[hashlib.md5(text.encode("utf-8")).hexdigest()] += 1
        if offset is None:
            break

    dup_texts = {h: c for h, c in text_hashes.items() if c > 1}
    dup_extra_points = sum(c - 1 for c in dup_texts.values())

    print(f"scrolled points: {total}")
    print(f"distinct source_urls: {len(sources)}")
    print(f"distinct text bodies: {len(text_hashes)}  (exact-duplicate bodies: {len(dup_texts)}, "
          f"extra points from dupes: {dup_extra_points})")
    print("\nsubcategory/category spread:")
    for k, c in subcats.most_common():
        print(f"  {c:6d}  {k}")
    print("\ncalendar academic_year spread (category=academic or subcategory=calendar):")
    for k, c in cal_years.most_common():
        print(f"  {c:6d}  {k}")
    print("\ntop 20 sources by point count:")
    for url, c in sources.most_common(20):
        print(f"  {c:6d}  {url}")

    client.close()


if __name__ == "__main__":
    main()
