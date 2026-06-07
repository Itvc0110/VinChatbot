from __future__ import annotations

import asyncio
import json
import logging
from collections import defaultdict, deque
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urldefrag, urlparse
from urllib.robotparser import RobotFileParser
from uuid import uuid4

import httpx

from vinchatbot.app.core.config import Settings, get_settings
from vinchatbot.app.ingest.assets import file_asset_records_from_links
from vinchatbot.app.ingest.normalizer import classify_domain, infer_source_kind, normalize_text
from vinchatbot.app.ingest.parsers import (
    PARSER_VERSION,
    extract_links_from_html,
    link_records_from_links,
    parse_binary_asset_bytes,
    parse_html,
    parse_markdown,
    parse_pdf_bytes,
    parse_spreadsheet_bytes,
)
from vinchatbot.app.schemas.document import (
    CrawlManifestEntry,
    CrawlTarget,
    LinkReference,
    RawDocument,
    SourceDocumentMetadata,
    StructuredRecord,
    stable_hash,
)

logger = logging.getLogger(__name__)


SEED_URLS = [
    "https://vinuni.edu.vn/student-gateway/",
    "https://vinuni.edu.vn/academic-calendar/",
    "https://policy.vinuni.edu.vn/wp-content/uploads/2025/06/VinUni-Academic-Calendar.pdf",
    "https://policy.vinuni.edu.vn/all-policies/",
    "https://policy.vinuni.edu.vn/whats-new/",
    "https://policy.vinuni.edu.vn/governance-and-legal/",
    "https://policy.vinuni.edu.vn/academic-affairs/",
    "https://policy.vinuni.edu.vn/research/",
    "https://policy.vinuni.edu.vn/student-affairs/",
    "https://policy.vinuni.edu.vn/external-affairs/",
    "https://policy.vinuni.edu.vn/information-management-and-technology/",
    "https://policy.vinuni.edu.vn/human-resources/",
    "https://policy.vinuni.edu.vn/financial-management/",
    "https://policy.vinuni.edu.vn/facilities-operations-and-safety/",
    "https://policy.vinuni.edu.vn/publication/",
]

VINUNI_PUBLIC_SUBDOMAINS = {
    "vinuni.edu.vn",
    "policy.vinuni.edu.vn",
    "registrar.vinuni.edu.vn",
    "library.vinuni.edu.vn",
    "admissions.vinuni.edu.vn",
    "cas.vinuni.edu.vn",
    "cbm.vinuni.edu.vn",
    "cecs.vinuni.edu.vn",
    "chs.vinuni.edu.vn",
    "experience.vinuni.edu.vn",
    "smarthealth.vinuni.edu.vn",
    "eship.vinuni.edu.vn",
    "scholarships.vinuni.edu.vn",
    "dei.vinuni.edu.vn",
    "marketing.vinuni.edu.vn",
    "alumni.vinuni.edu.vn",
    "sustainability.vinuni.edu.vn",
    "giving.vinuni.edu.vn",
}

PRIVATE_OR_LOGIN_HOSTS = {
    "my.vinuni.edu.vn",
    "sis.vinuni.edu.vn",
    "vinuni.instructure.com",
    "vinuniversity.sharepoint.com",
    "forms.office.com",
    "account.activedirectory.windowsazure.com",
    "vinuni.primo.exlibrisgroup.com",
}

NOISY_REFERENCE_HOSTS = {
    "www.facebook.com",
    "facebook.com",
    "www.instagram.com",
    "instagram.com",
    "www.linkedin.com",
    "vn.linkedin.com",
    "www.youtube.com",
    "youtube.com",
    "linktr.ee",
}

POLICY_LISTING_PATHS = {
    "/all-policies/",
    "/whats-new/",
    "/governance-and-legal/",
    "/academic-affairs/",
    "/research/",
    "/student-affairs/",
    "/external-affairs/",
    "/information-management-and-technology/",
    "/human-resources/",
    "/financial-management/",
    "/facilities-operations-and-safety/",
    "/publication/",
    "/publication-public/",
}


@dataclass
class CrawlResult:
    documents: list[RawDocument] = field(default_factory=list)
    manifest_entries: list[CrawlManifestEntry] = field(default_factory=list)
    link_references: list[LinkReference] = field(default_factory=list)
    structured_records: list[StructuredRecord] = field(default_factory=list)


class VinUniCrawler:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._robots_cache: dict[str, RobotFileParser | None] = {}
        self.last_result = CrawlResult()
        self.max_pages_total = self.settings.crawl_max_pages_total
        self.max_vinuni_pages_per_domain = self.settings.crawl_max_vinuni_pages_per_domain
        self.max_external_pages_per_domain = self.settings.crawl_max_external_pages_per_domain
        self.vinuni_max_depth = self.settings.crawl_vinuni_max_depth
        self.external_max_depth = self.settings.crawl_external_max_depth

    async def crawl(self, urls: list[str] | None = None, force: bool = False) -> list[RawDocument]:
        result = await self.crawl_full(urls=urls, force=force)
        return result.documents

    async def crawl_full(self, urls: list[str] | None = None, force: bool = False) -> CrawlResult:
        crawl_run_id = str(uuid4())
        previous_manifest = read_crawl_manifest(Path(self.settings.processed_data_dir) / "crawl_manifest.json")
        previous_link_references = read_link_references(
            Path(self.settings.processed_data_dir) / "link_references.json"
        )
        previous_links_by_source = _links_by_source(previous_link_references)
        seed_urls = urls or SEED_URLS
        logger.info(
            "Starting crawl run_id=%s seeds=%s max_pages=%s vinuni_depth=%s external_depth=%s",
            crawl_run_id,
            len(seed_urls),
            self.max_pages_total,
            self.vinuni_max_depth,
            self.external_max_depth,
        )
        frontier: deque[CrawlTarget] = deque(
            CrawlTarget(source_url=_canonicalize_url(url), crawl_depth=0, discovered_from="seed")
            for url in seed_urls
        )
        seen: set[str] = set()
        per_domain_counts: dict[str, int] = defaultdict(int)
        result = CrawlResult()

        headers = {"User-Agent": self.settings.crawl_user_agent}
        async with httpx.AsyncClient(
            timeout=self.settings.crawl_timeout_seconds,
            headers=headers,
            follow_redirects=True,
        ) as client:
            while frontier and len(result.manifest_entries) < self.max_pages_total:
                target = frontier.popleft()
                target.source_url = _canonicalize_url(target.source_url)
                if target.source_url in seen:
                    logger.debug("Skipping already-seen URL: %s", target.source_url)
                    continue
                seen.add(target.source_url)
                logger.info(
                    "Crawling depth=%s queued=%s processed=%s url=%s",
                    target.crawl_depth,
                    len(frontier),
                    len(result.manifest_entries),
                    target.source_url,
                )

                crawlable, reason = self._should_fetch_target(target, per_domain_counts)
                if not crawlable:
                    logger.info("Skipping URL reason=%s url=%s", reason, target.source_url)
                    result.link_references.append(self._target_to_link_reference(target, reason=reason))
                    continue

                robots_allowed = await self._can_fetch(client, target.source_url)
                if not robots_allowed:
                    logger.info("Skipping robots-disallowed URL: %s", target.source_url)
                    result.manifest_entries.append(self._skipped_manifest(target, "robots_disallowed", crawl_run_id))
                    result.link_references.append(self._target_to_link_reference(target, reason="robots_disallowed"))
                    continue

                try:
                    document, links, manifest_entry = await self._fetch_and_parse(
                        client=client,
                        target=target,
                        crawl_run_id=crawl_run_id,
                        robots_allowed=robots_allowed,
                    )
                except httpx.HTTPError as exc:
                    logger.warning("Failed to crawl %s: %s", target.source_url, exc)
                    result.manifest_entries.append(self._skipped_manifest(target, f"http_error:{exc}", crawl_run_id))
                    continue

                result.manifest_entries.append(manifest_entry)
                per_domain_counts[urlparse(document.source_url).netloc.lower()] += 1
                logger.info(
                    "Fetched status=%s kind=%s skipped=%s links=%s records=%s title=%s",
                    manifest_entry.http_status,
                    manifest_entry.source_kind,
                    manifest_entry.skipped,
                    len(links),
                    len(document.structured_records),
                    document.title,
                )

                if manifest_entry.skipped:
                    await asyncio.sleep(self.settings.crawl_rate_limit_seconds)
                    continue

                if not force and _manifest_is_unchanged(manifest_entry, previous_manifest):
                    manifest_entry.skipped = True
                    manifest_entry.skip_reason = "unchanged"
                    logger.info("Skipping unchanged URL: %s", manifest_entry.canonical_url)
                    previous_links = previous_links_by_source.get(manifest_entry.canonical_url, [])
                    if previous_links:
                        logger.info(
                            "Reusing %s previous link references for unchanged URL: %s",
                            len(previous_links),
                            manifest_entry.canonical_url,
                        )
                        result.link_references.extend(previous_links)
                        self._enqueue_previous_links(
                            frontier=frontier,
                            links=previous_links,
                            parent_url=manifest_entry.canonical_url,
                            parent_depth=target.crawl_depth,
                            seen=seen,
                        )
                    await asyncio.sleep(self.settings.crawl_rate_limit_seconds)
                    continue

                result.documents.append(document)
                result.structured_records.extend(document.structured_records)
                result.link_references.extend(links)

                for link in links:
                    if not link.should_crawl:
                        continue
                    child_target = CrawlTarget(
                        source_url=link.target_url,
                        parent_url=target.source_url,
                        crawl_depth=target.crawl_depth + 1,
                        anchor_text=link.anchor_text,
                        link_context=link.link_context,
                        discovered_from=target.source_url,
                        source_kind_hint=link.source_kind,
                    )
                    if _canonicalize_url(child_target.source_url) not in seen:
                        frontier.append(child_target)

                await asyncio.sleep(self.settings.crawl_rate_limit_seconds)

        self.last_result = result
        logger.info(
            "Finished crawl documents=%s manifest_entries=%s link_references=%s structured_records=%s",
            len(result.documents),
            len(result.manifest_entries),
            len(result.link_references),
            len(result.structured_records),
        )
        return result

    async def _fetch_and_parse(
        self,
        client: httpx.AsyncClient,
        target: CrawlTarget,
        crawl_run_id: str,
        robots_allowed: bool,
    ) -> tuple[RawDocument, list[LinkReference], CrawlManifestEntry]:
        response = await client.get(target.source_url)
        final_url = _canonicalize_url(str(response.url))
        content_type = response.headers.get("content-type", "")
        source_kind = infer_source_kind(final_url, content_type)
        source_metadata = self._source_metadata_from_response(
            target=target,
            final_url=final_url,
            response=response,
            source_kind=source_kind,
            robots_allowed=robots_allowed,
            crawl_run_id=crawl_run_id,
        )

        requires_login = _looks_login_required(response)
        noindex = _has_noindex(response)
        source_metadata.requires_login = requires_login
        source_metadata.noindex = noindex
        source_metadata.access_level = "login_required" if requires_login else "public"

        if response.status_code >= 400 or requires_login or noindex:
            reason = "login_required" if requires_login else ("noindex" if noindex else f"http_{response.status_code}")
            manifest_entry = _manifest_from_source(source_metadata, indexed=False, skipped=True, skip_reason=reason)
            empty_doc = RawDocument(
                source_url=target.source_url,
                canonical_url=final_url,
                title=target.anchor_text or final_url,
                document_type="link_reference",
                content="",
                metadata=source_metadata.model_dump(exclude_none=True),
                source_metadata=source_metadata,
            )
            return empty_doc, [self._target_to_link_reference(target, reason=reason)], manifest_entry

        lowered_content_type = content_type.lower()
        lowered_url = final_url.lower()
        if "pdf" in lowered_content_type or lowered_url.endswith(".pdf"):
            document = parse_pdf_bytes(response.content, final_url, source_metadata=source_metadata)
            links: list[LinkReference] = []
        elif source_kind in {"csv", "spreadsheet"}:
            document = parse_spreadsheet_bytes(
                response.content,
                final_url,
                content_type=content_type,
                source_metadata=source_metadata,
            )
            links = []
        elif source_kind == "markdown":
            document = parse_markdown(response.text, final_url, source_metadata=source_metadata)
            links = []
        elif source_kind in {"image_asset", "file_asset"} or _is_binary_response(content_type, final_url):
            document = parse_binary_asset_bytes(
                response.content,
                final_url,
                content_type=content_type,
                source_metadata=source_metadata,
            )
            links = []
        else:
            document = parse_html(response.text, final_url, source_metadata=source_metadata)
            links = self._classify_links(extract_links_from_html(response.text, final_url), document)
            if self.settings.image_download_enabled:
                links.extend(self._classify_links(self._image_links_from_document(document), document))
            document.structured_records.extend(link_records_from_links(links, document.parent_doc_id, document.metadata))
            document.structured_records.extend(file_asset_records_from_links(links, document.parent_doc_id, document.metadata))
            document.structured_records = _dedupe_structured_records(document.structured_records)

        source_metadata.content_hash = document.metadata.get("content_hash") or document.content_hash
        document.source_metadata = source_metadata
        document.metadata.update(source_metadata.model_dump(exclude_none=True))
        manifest_entry = _manifest_from_source(source_metadata, indexed=True, skipped=False)
        return document, links, manifest_entry

    def _source_metadata_from_response(
        self,
        target: CrawlTarget,
        final_url: str,
        response: httpx.Response,
        source_kind: str,
        robots_allowed: bool,
        crawl_run_id: str,
    ) -> SourceDocumentMetadata:
        domain, domain_type, source_trust = classify_domain(final_url)
        return SourceDocumentMetadata(
            source_id=stable_hash(final_url),
            source_url=target.source_url,
            final_url=final_url,
            canonical_url=final_url,
            source_kind=source_kind,
            domain=domain,
            domain_type=domain_type,
            source_trust=source_trust,
            parent_url=target.parent_url,
            crawl_depth=target.crawl_depth,
            anchor_text=target.anchor_text,
            link_context=target.link_context,
            discovered_from=target.discovered_from,
            http_status=response.status_code,
            content_type=response.headers.get("content-type"),
            mime_type=(response.headers.get("content-type") or "").split(";", 1)[0],
            file_size_bytes=len(response.content),
            etag=response.headers.get("etag"),
            last_modified_header=response.headers.get("last-modified"),
            robots_allowed=robots_allowed,
            parser_name="crawler",
            parser_version=PARSER_VERSION,
            crawl_run_id=crawl_run_id,
        )

    def _classify_links(self, links: list[LinkReference], document: RawDocument) -> list[LinkReference]:
        classified: list[LinkReference] = []
        for link in links:
            target = CrawlTarget(
                source_url=link.target_url,
                parent_url=document.source_url,
                crawl_depth=(document.source_metadata.crawl_depth if document.source_metadata else 0) + 1,
                anchor_text=link.anchor_text,
                link_context=link.link_context,
                discovered_from=document.source_url,
            )
            should_crawl, reason = self._should_fetch_target(target, defaultdict(int), from_link=True)
            link.should_crawl = should_crawl
            link.reason = reason
            link.requires_login = _is_private_or_login_url(link.target_url)
            link.source_kind = infer_source_kind(link.target_url, title=link.anchor_text)
            classified.append(link)
        return classified

    def _should_fetch_target(
        self,
        target: CrawlTarget,
        per_domain_counts: dict[str, int],
        from_link: bool = False,
    ) -> tuple[bool, str | None]:
        parsed = urlparse(target.source_url)
        host = parsed.netloc.lower()
        if parsed.scheme not in {"http", "https"}:
            return False, "unsupported_scheme"
        if _is_private_or_login_url(target.source_url):
            return False, "private_or_login_required"
        if host in NOISY_REFERENCE_HOSTS:
            return False, "noisy_reference_domain"

        domain, domain_type, _ = classify_domain(target.source_url)
        if domain_type == "policy":
            if _is_policy_allowed_path(parsed.path):
                return True, None
            return False, "policy_path_out_of_scope"

        if host in VINUNI_PUBLIC_SUBDOMAINS:
            if target.crawl_depth > self.vinuni_max_depth:
                return False, "vinuni_depth_cap"
            if not from_link and per_domain_counts.get(host, 0) >= self.max_vinuni_pages_per_domain:
                return False, "vinuni_domain_cap"
            return True, None

        if target.crawl_depth > self.external_max_depth:
            return False, "external_depth_cap"
        if not from_link and per_domain_counts.get(host, 0) >= self.max_external_pages_per_domain:
            return False, "external_domain_cap"
        return True, None

    async def _can_fetch(self, client: httpx.AsyncClient, url: str) -> bool:
        parsed = urlparse(url)
        base = f"{parsed.scheme}://{parsed.netloc}"
        if base not in self._robots_cache:
            robots_url = f"{base}/robots.txt"
            parser = RobotFileParser()
            try:
                response = await client.get(robots_url)
                if response.status_code >= 400:
                    self._robots_cache[base] = None
                    return True
                parser.parse(response.text.splitlines())
            except httpx.HTTPError:
                self._robots_cache[base] = None
                return True
            self._robots_cache[base] = parser
        parser = self._robots_cache[base]
        if parser is None:
            return True
        return parser.can_fetch(self.settings.crawl_user_agent, url)

    def _target_to_link_reference(self, target: CrawlTarget, reason: str | None = None) -> LinkReference:
        domain, domain_type, source_trust = classify_domain(target.source_url)
        return LinkReference(
            source_url=target.parent_url or target.source_url,
            target_url=target.source_url,
            anchor_text=target.anchor_text,
            link_context=target.link_context,
            discovered_from=target.discovered_from,
            domain=domain,
            domain_type=domain_type,
            source_kind="link_reference",
            source_trust=source_trust,
            requires_login=_is_private_or_login_url(target.source_url),
            should_crawl=False,
            reason=reason,
        )

    @staticmethod
    def _image_links_from_document(document: RawDocument) -> list[LinkReference]:
        links: list[LinkReference] = []
        for record in document.structured_records:
            if record.record_type != "image_asset":
                continue
            asset_url = record.data.get("asset_url")
            if not asset_url:
                continue
            domain, domain_type, source_trust = classify_domain(asset_url)
            links.append(
                LinkReference(
                    source_url=document.source_url,
                    target_url=_canonicalize_url(asset_url),
                    anchor_text=record.title,
                    link_context=record.data.get("description") or record.data.get("nearby_text"),
                    section_path=list(record.data.get("section_path") or []),
                    discovered_from=document.source_url,
                    domain=domain,
                    domain_type=domain_type,
                    source_kind=infer_source_kind(asset_url),
                    source_trust=source_trust,
                )
            )
        return links

    @staticmethod
    def _enqueue_previous_links(
        frontier: deque[CrawlTarget],
        links: list[LinkReference],
        parent_url: str,
        parent_depth: int,
        seen: set[str],
    ) -> None:
        for link in links:
            if not link.should_crawl:
                continue
            child_url = _canonicalize_url(link.target_url)
            if child_url in seen:
                continue
            frontier.append(
                CrawlTarget(
                    source_url=child_url,
                    parent_url=parent_url,
                    crawl_depth=parent_depth + 1,
                    anchor_text=link.anchor_text,
                    link_context=link.link_context,
                    discovered_from=parent_url,
                    source_kind_hint=link.source_kind,
                )
            )

    def _skipped_manifest(self, target: CrawlTarget, reason: str, crawl_run_id: str) -> CrawlManifestEntry:
        canonical_url = _canonicalize_url(target.source_url)
        domain, _, _ = classify_domain(canonical_url)
        return CrawlManifestEntry(
            source_id=stable_hash(canonical_url),
            source_url=target.source_url,
            final_url=canonical_url,
            canonical_url=canonical_url,
            source_kind=infer_source_kind(canonical_url),
            domain=domain,
            crawl_depth=target.crawl_depth,
            indexed=False,
            skipped=True,
            skip_reason=reason,
            parser_version=PARSER_VERSION,
            crawl_run_id=crawl_run_id,
        )


def write_raw_documents(documents: list[RawDocument], output_dir: str | Path) -> list[Path]:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for document in documents:
        path = output_path / f"{document.parent_doc_id}.json"
        path.write_text(document.model_dump_json(indent=2), encoding="utf-8")
        paths.append(path)
    return paths


def read_raw_documents(input_dir: str | Path) -> list[RawDocument]:
    documents: list[RawDocument] = []
    for path in Path(input_dir).glob("*.json"):
        documents.append(RawDocument.model_validate(json.loads(path.read_text(encoding="utf-8"))))
    return documents


def read_link_references(input_path: str | Path) -> list[LinkReference]:
    path = Path(input_path)
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [LinkReference.model_validate(item) for item in payload]


def read_structured_records(input_path: str | Path) -> list[StructuredRecord]:
    path = Path(input_path)
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [StructuredRecord.model_validate(item) for item in payload]


def write_crawl_manifest(entries: list[CrawlManifestEntry], output_path: str | Path) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps([entry.model_dump() for entry in entries], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def read_crawl_manifest(input_path: str | Path) -> dict[str, CrawlManifestEntry]:
    path = Path(input_path)
    if not path.exists():
        return {}
    entries = [CrawlManifestEntry.model_validate(item) for item in json.loads(path.read_text(encoding="utf-8"))]
    return {entry.canonical_url: entry for entry in entries}


def write_link_references(references: list[LinkReference], output_path: str | Path) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps([reference.model_dump() for reference in references], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def write_structured_records(records: list[StructuredRecord], output_path: str | Path) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps([record.model_dump() for record in records], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _manifest_from_source(
    source: SourceDocumentMetadata,
    indexed: bool,
    skipped: bool,
    skip_reason: str | None = None,
) -> CrawlManifestEntry:
    return CrawlManifestEntry(
        source_id=source.source_id,
        source_url=source.source_url,
        final_url=source.final_url,
        canonical_url=source.canonical_url,
        source_kind=source.source_kind,
        domain=source.domain,
        crawl_depth=source.crawl_depth,
        http_status=source.http_status,
        fetched_at=source.fetched_at,
        content_hash=source.content_hash,
        parser_name=source.parser_name,
        parser_version=source.parser_version,
        indexed=indexed,
        skipped=skipped,
        skip_reason=skip_reason,
        crawl_run_id=source.crawl_run_id,
    )


def _manifest_is_unchanged(
    entry: CrawlManifestEntry,
    previous_manifest: dict[str, CrawlManifestEntry],
) -> bool:
    previous = previous_manifest.get(entry.canonical_url)
    if not previous:
        return False
    return (
        previous.content_hash == entry.content_hash
        and previous.parser_version == entry.parser_version
        and entry.content_hash is not None
    )


def _links_by_source(links: list[LinkReference]) -> dict[str, list[LinkReference]]:
    grouped: dict[str, list[LinkReference]] = defaultdict(list)
    for link in links:
        grouped[_canonicalize_url(link.source_url)].append(link)
    return grouped


def _canonicalize_url(url: str) -> str:
    url, _ = urldefrag(url)
    return url.strip()


def _is_policy_allowed_path(path: str) -> bool:
    normalized = path if path.endswith("/") else f"{path}/"
    return (
        normalized in POLICY_LISTING_PATHS
        or path.startswith("/all-policies/")
        or path.startswith("/publication/")
        or path.startswith("/wp-content/uploads/")
    )


def _is_private_or_login_url(url: str) -> bool:
    host = urlparse(url).netloc.lower()
    lowered = url.lower()
    if host in PRIVATE_OR_LOGIN_HOSTS:
        return True
    return any(marker in lowered for marker in ["login", "signin", "sso", "sharepoint.com", "forms.office.com"])


def _is_binary_response(content_type: str, url: str) -> bool:
    lowered_content_type = (content_type or "").lower()
    if lowered_content_type.startswith(("text/html", "text/plain", "application/xhtml+xml")):
        return False
    if "json" in lowered_content_type or "xml" in lowered_content_type:
        return False
    path = urlparse(url).path.lower()
    if path.endswith((".html", ".htm", "/")):
        return False
    return bool(lowered_content_type) or path.endswith(
        (
            ".png",
            ".jpg",
            ".jpeg",
            ".gif",
            ".webp",
            ".bmp",
            ".tif",
            ".tiff",
            ".svg",
            ".doc",
            ".docx",
            ".ppt",
            ".pptx",
            ".zip",
        )
    )


def _dedupe_structured_records(records: list[StructuredRecord]) -> list[StructuredRecord]:
    deduped: dict[str, StructuredRecord] = {}
    for record in records:
        deduped[record.record_id] = record
    return list(deduped.values())


def _looks_login_required(response: httpx.Response) -> bool:
    if response.status_code in {401, 403}:
        return True
    final_url = str(response.url).lower()
    if any(marker in final_url for marker in ["login", "signin", "sso"]):
        return True
    content_type = response.headers.get("content-type", "").lower()
    if "text/html" not in content_type:
        return False
    sample = normalize_text(response.text[:5000]).lower()
    login_markers = [
        "please sign in",
        "sign in with your vinuni id",
        "login",
        "single sign-on",
        "microsoft sign in",
        "canvas learning management system",
    ]
    return any(marker in sample for marker in login_markers)


def _has_noindex(response: httpx.Response) -> bool:
    robots_header = response.headers.get("x-robots-tag", "").lower()
    if "noindex" in robots_header:
        return True
    content_type = response.headers.get("content-type", "").lower()
    if "text/html" not in content_type:
        return False
    sample = response.text[:10000].lower()
    return 'name="robots"' in sample and "noindex" in sample
