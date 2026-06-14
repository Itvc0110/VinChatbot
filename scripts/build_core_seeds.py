"""Build a focused seed list for the Phase 0 re-crawl.

Harvests the policy *detail* URLs already extracted into structured_records.json
(the 334 `policy_listing` records carry `detail_url`), combines them with the built-in
seeds and the core document URLs (academic calendar PDF, financial tariff, code of
conduct), and writes data/processed/core_seeds.json for `crawl_seed.py --seed-file`.

The previous crawl stopped at a 50-page cap before reaching these; seeding them directly
guarantees the high-value content is fetched.
"""

from __future__ import annotations

import json
from pathlib import Path

from vinchatbot.app.core.config import get_settings
from vinchatbot.app.ingest.crawler import SEED_URLS

# Core documents we explicitly want even if discovery misses them.
CORE_DOC_URLS = [
    "https://policy.vinuni.edu.vn/wp-content/uploads/2025/06/VinUni-Academic-Calendar.pdf",
]


def _detail_urls_from_records(records_path: Path) -> list[str]:
    if not records_path.exists():
        return []
    records = json.loads(records_path.read_text(encoding="utf-8"))
    urls: list[str] = []
    for record in records:
        if record.get("record_type") != "policy_listing":
            continue
        detail_url = (record.get("data") or {}).get("detail_url")
        if isinstance(detail_url, str) and detail_url.startswith("http"):
            urls.append(detail_url.strip())
    return urls


def main() -> None:
    settings = get_settings()
    processed = Path(settings.processed_data_dir)
    detail_urls = _detail_urls_from_records(processed / "structured_records.json")

    # Preserve order while de-duplicating: built-in seeds, core docs, then policy details.
    seen: set[str] = set()
    seeds: list[str] = []
    for url in [*SEED_URLS, *CORE_DOC_URLS, *detail_urls]:
        if url and url not in seen:
            seen.add(url)
            seeds.append(url)

    output_path = processed / "core_seeds.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(seeds, ensure_ascii=False, indent=2), encoding="utf-8")

    print(
        json.dumps(
            {
                "built_in_seeds": len(SEED_URLS),
                "core_docs": len(CORE_DOC_URLS),
                "policy_detail_urls": len(detail_urls),
                "total_seeds": len(seeds),
                "output": str(output_path),
            }
        )
    )


if __name__ == "__main__":
    main()
