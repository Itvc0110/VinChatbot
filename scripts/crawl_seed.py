from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from vinchatbot.app.core.config import get_settings
from vinchatbot.app.ingest.crawler import (
    VinUniCrawler,
    read_crawl_manifest,
    read_link_references,
    read_structured_records,
    write_crawl_manifest,
    write_link_references,
    write_raw_documents,
    write_structured_records,
)
from vinchatbot.app.schemas.document import CrawlManifestEntry, LinkReference, StructuredRecord


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Crawl public VinUni sources and write crawl artifacts.")
    parser.add_argument(
        "--seed-url",
        action="append",
        dest="seed_urls",
        help="Seed URL to crawl. Can be passed multiple times. Defaults to built-in VinUni seeds.",
    )
    parser.add_argument("--max-pages", type=int, help="Override CRAWL_MAX_PAGES_TOTAL for this run.")
    parser.add_argument("--rate-limit", type=float, help="Override CRAWL_RATE_LIMIT_SECONDS for this run.")
    parser.add_argument("--force", action="store_true", help="Reprocess unchanged documents.")
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Console log level.",
    )
    return parser.parse_args()


def configure_script_logging(level_name: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level_name.upper()),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        stream=sys.stdout,
    )


async def main() -> None:
    args = parse_args()
    configure_script_logging(args.log_level)
    settings = get_settings()
    if args.max_pages is not None:
        settings.crawl_max_pages_total = args.max_pages
    if args.rate_limit is not None:
        settings.crawl_rate_limit_seconds = args.rate_limit

    crawler = VinUniCrawler(settings)
    result = await crawler.crawl_full(urls=args.seed_urls, force=args.force)
    paths = write_raw_documents(result.documents, settings.raw_data_dir)
    manifest_path = f"{settings.processed_data_dir}/crawl_manifest.json"
    link_refs_path = f"{settings.processed_data_dir}/link_references.json"
    records_path = f"{settings.processed_data_dir}/structured_records.json"
    write_crawl_manifest(
        merge_manifest_entries(
            list(read_crawl_manifest(manifest_path).values()),
            result.manifest_entries,
        ),
        manifest_path,
    )
    write_link_references(
        merge_link_references(read_link_references(link_refs_path), result.link_references),
        link_refs_path,
    )
    write_structured_records(
        merge_structured_records(read_structured_records(records_path), result.structured_records),
        records_path,
    )

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
    print(
        {
            "raw_data_dir": settings.raw_data_dir,
            "crawl_manifest": manifest_path,
            "link_references": link_refs_path,
            "structured_records": records_path,
        }
    )
    if not result.documents:
        logging.warning(
            "No raw documents were written. Check crawl_manifest.json skip_reason values. "
            "If skip_reason contains connection errors, verify network access."
        )


def merge_manifest_entries(
    previous: list[CrawlManifestEntry],
    current: list[CrawlManifestEntry],
) -> list[CrawlManifestEntry]:
    merged = {entry.canonical_url: entry for entry in previous}
    for entry in current:
        merged[entry.canonical_url] = entry
    return list(merged.values())


def merge_link_references(
    previous: list[LinkReference],
    current: list[LinkReference],
) -> list[LinkReference]:
    merged = {
        (
            reference.source_url,
            reference.target_url,
            reference.anchor_text,
            reference.link_context,
        ): reference
        for reference in previous
    }
    for reference in current:
        merged[
            (
                reference.source_url,
                reference.target_url,
                reference.anchor_text,
                reference.link_context,
            )
        ] = reference
    return list(merged.values())


def merge_structured_records(
    previous: list[StructuredRecord],
    current: list[StructuredRecord],
) -> list[StructuredRecord]:
    merged = {record.record_id: record for record in previous}
    for record in current:
        merged[record.record_id] = record
    return list(merged.values())


if __name__ == "__main__":
    asyncio.run(main())
