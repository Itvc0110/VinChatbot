from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path
from urllib.parse import urldefrag

from vinchatbot.app.core.config import get_settings
from vinchatbot.app.ingest.crawler import (
    VinUniCrawler,
    read_crawl_manifest,
    read_link_references,
    read_structured_records,
    write_crawl_coverage_report,
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
    parser.add_argument(
        "--seed-file",
        help="Path to a JSON file containing a list of seed URLs (e.g. data/processed/core_seeds.json).",
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

    seed_urls = list(args.seed_urls or [])
    if args.seed_file:
        seed_urls.extend(load_seed_file(args.seed_file))
    seed_urls = seed_urls or None  # None lets the crawler use its built-in SEED_URLS

    crawler = VinUniCrawler(settings)
    result = await crawler.crawl_full(urls=seed_urls, force=args.force)
    paths = write_raw_documents(result.documents, settings.raw_data_dir)

    if seed_urls:
        report_seed_coverage(seed_urls, result.manifest_entries)
    manifest_path = f"{settings.processed_data_dir}/crawl_manifest.json"
    link_refs_path = f"{settings.processed_data_dir}/link_references.json"
    records_path = f"{settings.processed_data_dir}/structured_records.json"
    coverage_path = f"{settings.processed_data_dir}/crawl_coverage_report.json"
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
    write_crawl_coverage_report(
        result.documents,
        result.manifest_entries,
        result.link_references,
        coverage_path,
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
            "crawl_coverage_report": coverage_path,
        }
    )
    if not result.documents:
        logging.warning(
            "No raw documents were written. Check crawl_manifest.json skip_reason values. "
            "If skip_reason contains connection errors, verify network access."
        )


def load_seed_file(path: str) -> list[str]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"Seed file {path} must contain a JSON list of URLs.")
    return [str(url).strip() for url in payload if str(url).strip()]


def report_seed_coverage(
    seed_urls: list[str],
    manifest_entries: list[CrawlManifestEntry],
) -> None:
    def _norm(url: str) -> str:
        return urldefrag(url.strip())[0].rstrip("/")

    reached = set()
    for entry in manifest_entries:
        for value in (entry.source_url, entry.final_url, entry.canonical_url):
            if value:
                reached.add(_norm(value))
    missing = [url for url in seed_urls if _norm(url) not in reached]
    logging.info("Seed coverage: %s/%s seeds reached the manifest.", len(seed_urls) - len(missing), len(seed_urls))
    if missing:
        logging.warning("Seeds NOT in this run's manifest (%s):", len(missing))
        for url in missing[:50]:
            logging.warning("  missing seed: %s", url)


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
