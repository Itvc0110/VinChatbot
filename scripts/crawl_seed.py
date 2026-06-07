from __future__ import annotations

import asyncio

from vinchatbot.app.core.config import get_settings
from vinchatbot.app.ingest.crawler import (
    VinUniCrawler,
    write_crawl_manifest,
    write_link_references,
    write_raw_documents,
    write_structured_records,
)


async def main() -> None:
    settings = get_settings()
    crawler = VinUniCrawler(settings)
    result = await crawler.crawl_full()
    paths = write_raw_documents(result.documents, settings.raw_data_dir)
    write_crawl_manifest(result.manifest_entries, f"{settings.processed_data_dir}/crawl_manifest.json")
    write_link_references(result.link_references, f"{settings.processed_data_dir}/link_references.json")
    write_structured_records(result.structured_records, f"{settings.processed_data_dir}/structured_records.json")
    for path in paths:
        print(path)
    print(
        {
            "documents": len(result.documents),
            "manifest_entries": len(result.manifest_entries),
            "link_references": len(result.link_references),
            "structured_records": len(result.structured_records),
        }
    )


if __name__ == "__main__":
    asyncio.run(main())
