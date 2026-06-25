"""Build a COMPACT structured-lookup index from the full structured records.

The full data/processed/structured_records.json is ~150 MB (≈48k records, mostly link/image/table
noise). The structured lookup needs only `calendar_event` records + financial `table_record`s (~100).
Loading the whole file at serving time OOMs under the agent process's memory pressure (graph + fastembed
+ 150 MB) → the index silently fails to build → lookups disabled. This script filters once (run when RAM
is free) into a tiny data/processed/structured_index.json that the app loads cheaply and reliably.

Usage: py scripts/build_structured_index.py
"""

from __future__ import annotations

import json
from pathlib import Path

from vinchatbot.app.core.config import get_settings
from vinchatbot.app.rag.structured_lookup import (
    is_authoritative_structured_source,
    stream_json_array,
)

KEEP_CALENDAR = "calendar_event"


def _is_target(record: dict) -> bool:
    """A calendar_event or a financial table_record — the only records the deterministic lookup serves."""
    rt = record.get("record_type")
    return rt == KEEP_CALENDAR or (
        rt == "table_record" and (record.get("metadata") or {}).get("subcategory") == "financial"
    )


def main() -> None:
    settings = get_settings()
    processed = Path(settings.processed_data_dir)
    src = processed / "structured_records.json"
    dst = processed / "structured_index.json"
    if not src.exists():
        raise SystemExit(f"source not found: {src}")

    kept = []
    skipped_non_authoritative = 0
    for record in stream_json_array(src):  # streamed → builds even with little free RAM
        if not _is_target(record):
            continue
        # Authoritative-source only: a calendar/fee record must come from policy.vinuni (the calendar PDF +
        # tariff). A college/admissions/marketing page mentioning a date or amount must NEVER feed the
        # deterministic lookup (it would surface a wrong, high-confidence answer that bypasses rerank).
        if not is_authoritative_structured_source(record):
            skipped_non_authoritative += 1
            continue
        kept.append(record)

    dst.write_text(json.dumps(kept, ensure_ascii=False), encoding="utf-8")
    cal = sum(1 for r in kept if r.get("record_type") == KEEP_CALENDAR)
    fee = sum(1 for r in kept if r.get("record_type") == "table_record")
    size_kb = dst.stat().st_size / 1024
    print(
        f"wrote {dst} — {len(kept)} records ({cal} calendar_event, {fee} financial table_record), "
        f"{size_kb:.0f} KB; skipped {skipped_non_authoritative} non-authoritative (non-policy) records"
    )


if __name__ == "__main__":
    main()
