from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from vinchatbot.app.ingest.normalizer import (
    classify_domain,
    infer_category,
    infer_source_kind,
    normalize_text,
)
from vinchatbot.app.schemas.document import (
    CalendarEvent,
    LinkReference,
    RawDocument,
    SourceDocumentMetadata,
    StructuredRecord,
    stable_hash,
)

PARSER_VERSION = "v2"
MONTHS = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "sept": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}
DATE_TEXT_PATTERN = re.compile(
    r"(?P<date>"
    r"\b\d{1,2}(?:-\d{1,2})?[- ](?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)"
    r"(?:[- ]\d{2,4})?"
    r"(?:-\d{1,2}[- ](?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)(?:[- ]\d{2,4})?)?"
    r"|\b\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?"
    r"|\b\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\s+\d{4}"
    r")",
    flags=re.IGNORECASE,
)
DATE_VALUE_PATTERN = re.compile(r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)", re.I)
VND_PATTERN = re.compile(r"(?P<amount>\d[\d,.\s]*)\s*(?P<currency>VND|VNĐ)", re.IGNORECASE)


def parse_html(
    content: str,
    source_url: str,
    source_metadata: SourceDocumentMetadata | None = None,
) -> RawDocument:
    title = source_url
    soup = BeautifulSoup(content, "html.parser")
    if soup.title and soup.title.text:
        title = normalize_text(soup.title.text)

    source_kind = source_metadata.source_kind if source_metadata else infer_source_kind(source_url, title=title)
    extracted = _extract_html_text(content, soup, source_kind)
    metadata = _base_raw_metadata(source_url, title, source_kind, source_metadata)
    metadata.update(extract_policy_detail_metadata(content, source_url))
    metadata["link_count"] = len(extract_links_from_html(content, source_url))

    structured_records = extract_structured_records_from_html(content, source_url, metadata)

    if source_metadata:
        source_metadata.parser_name = "html"
        source_metadata.parser_version = PARSER_VERSION
        source_metadata.content_hash = stable_hash(extracted or "")

    return RawDocument(
        source_url=source_url,
        canonical_url=metadata.get("canonical_url", source_url),
        title=metadata.get("document_title") or title,
        document_type=source_kind if source_kind != "external_public_page" else "html",
        content=normalize_text(extracted or ""),
        metadata=metadata,
        source_metadata=source_metadata,
        structured_records=structured_records,
    )


def _extract_html_text(content: str, soup: BeautifulSoup, source_kind: str) -> str:
    if source_kind in {
        "gateway_page",
        "policy_listing",
        "policy_html",
        "financial_policy",
        "academic_catalog",
        "calendar_page",
        "registrar_page",
        "library_page",
    }:
        return _extract_structured_html_text(soup)

    extracted = None
    try:
        import trafilatura

        extracted = trafilatura.extract(content, include_links=False, include_tables=True)
    except ImportError:
        extracted = None

    if not extracted:
        extracted = _extract_structured_html_text(soup)
    return extracted


def _extract_structured_html_text(soup: BeautifulSoup) -> str:
    for tag in soup(["script", "style", "nav", "footer", "header", "noscript"]):
        tag.decompose()
    headings_and_text: list[str] = []
    for element in soup.find_all(["h1", "h2", "h3", "h4", "h5", "p", "li", "td", "th"]):
        text = normalize_text(element.get_text(" ", strip=True))
        if not text:
            continue
        if element.name in {"h1", "h2", "h3", "h4", "h5"}:
            level = int(element.name[1])
            headings_and_text.append(f"{'#' * level} {text}")
        else:
            headings_and_text.append(text)
    return "\n\n".join(headings_and_text)


def parse_pdf_bytes(
    content: bytes,
    source_url: str,
    title: str | None = None,
    source_metadata: SourceDocumentMetadata | None = None,
) -> RawDocument:
    try:
        import fitz
    except ImportError as exc:
        raise RuntimeError("Install pymupdf to parse PDF files.") from exc

    pages: list[str] = []
    with fitz.open(stream=content, filetype="pdf") as document:
        meta_title = document.metadata.get("title") if document.metadata else None
        title = title or meta_title or Path(source_url).name or source_url
        for index, page in enumerate(document, start=1):
            page_text = normalize_text(page.get_text("text"))
            if page_text:
                pages.append(f"# Trang {index}\n{page_text}")

    source_kind = source_metadata.source_kind if source_metadata else infer_source_kind(source_url, "application/pdf", title)
    extracted = normalize_text("\n\n".join(pages))
    metadata = _base_raw_metadata(source_url, title, source_kind, source_metadata)
    metadata["file_size_bytes"] = len(content)
    metadata["page_count"] = len(pages)
    if source_kind == "calendar_pdf":
        metadata.setdefault("academic_year", infer_academic_year(extracted, source_url))

    raw = RawDocument(
        source_url=source_url,
        canonical_url=metadata.get("canonical_url", source_url),
        title=normalize_text(title),
        document_type=source_kind if source_kind != "external_public_page" else "pdf",
        content=extracted,
        metadata=metadata,
        source_metadata=source_metadata,
    )
    raw.structured_records = structured_records_from_raw(raw)
    if source_metadata:
        source_metadata.parser_name = "pdf"
        source_metadata.parser_version = PARSER_VERSION
        source_metadata.content_hash = raw.content_hash
        source_metadata.file_size_bytes = len(content)
    return raw


DATE_PATTERN = DATE_TEXT_PATTERN


def extract_calendar_events(raw: RawDocument) -> list[CalendarEvent]:
    events: list[CalendarEvent] = []
    academic_year = raw.metadata.get("academic_year")
    term_hint = raw.metadata.get("term")
    current_page: int | None = None

    for line in raw.content.splitlines():
        stripped = normalize_text(line)
        if not stripped:
            continue
        page_match = re.match(r"#\s*Trang\s+(\d+)", stripped, flags=re.IGNORECASE)
        if page_match:
            current_page = int(page_match.group(1))
            continue
        match = DATE_PATTERN.search(stripped)
        if not match:
            continue
        lowered = stripped.lower()
        if not any(
            keyword in lowered
            for keyword in [
                "instruction",
                "deadline",
                "drop",
                "add",
                "exam",
                "holiday",
                "spring",
                "fall",
                "summer",
                "học kỳ",
                "kỳ thi",
                "hạn",
            ]
        ):
            continue
        term = term_hint
        if "fall" in lowered:
            term = "Fall"
        elif "spring" in lowered:
            term = "Spring"
        elif "summer" in lowered:
            term = "Summer"
        date_text = match.group("date")
        date_start_iso, date_end_iso = normalize_date_range(date_text, raw.metadata.get("academic_year"))
        events.append(
            CalendarEvent(
                event_name=stripped,
                date_start=date_text,
                event_type=infer_event_type(stripped),
                date_text_original=date_text,
                date_start_iso=date_start_iso,
                date_end_iso=date_end_iso,
                academic_year=academic_year,
                term=term,
                source_url=raw.source_url,
                page_number=current_page,
            )
        )
    return events


def _base_raw_metadata(
    source_url: str,
    title: str,
    source_kind: str,
    source_metadata: SourceDocumentMetadata | None = None,
) -> dict[str, Any]:
    domain, domain_type, source_trust = classify_domain(source_url)
    category, subcategory = infer_category(source_url, title)
    if source_kind == "policy_listing":
        category, subcategory = "policy", "listing"
    elif source_kind == "gateway_page":
        category, subcategory = "gateway", "student_support"
    elif source_kind in {"calendar_page", "calendar_pdf"}:
        category, subcategory = "academic", "calendar"
    elif source_kind == "financial_policy":
        category, subcategory = "student_affairs", "financial"
    elif source_kind == "academic_catalog":
        category, subcategory = "academic", "catalog"
    elif source_kind == "registrar_page":
        category, subcategory = "academic", "registrar"
    elif source_kind == "library_page":
        category, subcategory = "student_services", "library"

    metadata = {
        "source_kind": source_kind,
        "source_id": stable_hash(source_url),
        "canonical_url": source_url,
        "document_title": normalize_text(title),
        "domain": domain,
        "domain_type": domain_type,
        "source_trust": source_trust,
        "category": category,
        "subcategory": subcategory,
        "parser_name": "html",
        "parser_version": PARSER_VERSION,
    }
    if source_metadata:
        metadata.update(source_metadata.model_dump(exclude_none=True))
        metadata["source_id"] = source_metadata.source_id
        metadata["canonical_url"] = source_metadata.canonical_url
    return metadata


def extract_links_from_html(content: str, source_url: str) -> list[LinkReference]:
    soup = BeautifulSoup(content, "html.parser")
    links: list[LinkReference] = []
    section_path: list[str] = []
    for element in soup.find_all(["h1", "h2", "h3", "h4", "a"]):
        if element.name in {"h1", "h2", "h3", "h4"}:
            level = int(element.name[1])
            heading = normalize_text(element.get_text(" ", strip=True))
            if heading:
                section_path = section_path[: level - 1]
                section_path.append(heading)
            continue
        href = element.get("href")
        if not href:
            continue
        target_url = urljoin(source_url, href)
        if target_url.startswith("mailto:") or target_url.startswith("tel:"):
            continue
        anchor_text = normalize_text(element.get_text(" ", strip=True))
        context = _nearby_text(element)
        domain, domain_type, source_trust = classify_domain(target_url)
        links.append(
            LinkReference(
                source_url=source_url,
                target_url=target_url.split("#", 1)[0],
                anchor_text=anchor_text or None,
                link_context=context or None,
                section_path=list(section_path),
                discovered_from=source_url,
                domain=domain,
                domain_type=domain_type,
                source_trust=source_trust,
            )
        )
    return links


def parse_policy_listing_records(content: str, source_url: str, metadata: dict[str, Any] | None = None) -> list[StructuredRecord]:
    metadata = metadata or {}
    soup = BeautifulSoup(content, "html.parser")
    records: list[StructuredRecord] = []
    for link in soup.find_all("a", href=True):
        href = str(link["href"])
        if "/all-policies/" not in href and "/publication/" not in href:
            continue
        title = normalize_text(link.get_text(" ", strip=True))
        if not title or title.lower() in {"all policies", "publication / public"}:
            continue
        target_url = urljoin(source_url, href)
        row_text = normalize_text(link.find_parent("tr").get_text(" ", strip=True)) if link.find_parent("tr") else _nearby_text(link)
        dates = re.findall(r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{2},\s+\d{4}", row_text)
        policy_code = _extract_policy_code(row_text, title, dates)
        data = {
            "policy_title": title,
            "policy_code": policy_code,
            "date_issued": dates[0] if dates else None,
            "date_last_updated": dates[1] if len(dates) > 1 else (dates[0] if dates else None),
            "detail_url": target_url,
            "listing_category": metadata.get("subcategory") or _listing_category_from_url(source_url),
        }
        record_id = stable_hash(f"policy_listing:{source_url}:{target_url}:{policy_code or title}")
        records.append(
            StructuredRecord(
                record_id=record_id,
                record_type="policy_listing",
                parent_doc_id=stable_hash(source_url),
                source_url=source_url,
                title=title,
                data=data,
                metadata=metadata,
            )
        )
    return _dedupe_records(records)


def extract_policy_detail_metadata(content: str, source_url: str) -> dict[str, Any]:
    soup = BeautifulSoup(content, "html.parser")
    text_lines = [normalize_text(line) for line in soup.get_text("\n", strip=True).splitlines()]
    text_lines = [line for line in text_lines if line]
    result: dict[str, Any] = {}
    h1 = soup.find("h1")
    if h1:
        result["document_title"] = normalize_text(h1.get_text(" ", strip=True))

    label_map = {
        "Reference Number": "reference_number",
        "Document Type": "document_status",
        "Issuing By": "issuing_unit",
        "Issuing Date": "issued_date",
        "Date Issued": "issued_date",
        "Date Last Updated": "updated_date",
        "Applying for": "applying_for",
        "Security Classification": "security_classification",
    }
    for index, line in enumerate(text_lines):
        clean_label = line.rstrip(":")
        if clean_label not in label_map:
            continue
        value = _next_value(text_lines, index + 1)
        if value:
            result[label_map[clean_label]] = value

    pdf_link = None
    for link in soup.find_all("a", href=True):
        href = urljoin(source_url, str(link["href"]))
        if href.lower().endswith(".pdf") or "wp-content/uploads" in href:
            pdf_link = href
    if pdf_link:
        result["pdf_url"] = pdf_link
    return result


def extract_structured_records_from_html(
    content: str,
    source_url: str,
    metadata: dict[str, Any] | None = None,
) -> list[StructuredRecord]:
    metadata = metadata or {}
    source_kind = metadata.get("source_kind") or infer_source_kind(source_url)
    records: list[StructuredRecord] = []
    if source_kind == "policy_listing":
        records.extend(parse_policy_listing_records(content, source_url, metadata))

    raw = RawDocument(
        source_url=source_url,
        canonical_url=metadata.get("canonical_url", source_url),
        title=metadata.get("document_title") or source_url,
        document_type=source_kind if source_kind != "external_public_page" else "html",
        content=_extract_structured_html_text(BeautifulSoup(content, "html.parser")),
        metadata=metadata,
    )
    records.extend(structured_records_from_raw(raw))
    if source_kind in {"gateway_page", "registrar_page", "library_page", "external_public_page"}:
        records.extend(link_records_from_links(extract_links_from_html(content, source_url), raw.parent_doc_id, metadata))
    return _dedupe_records(records)


def structured_records_from_raw(raw: RawDocument) -> list[StructuredRecord]:
    records: list[StructuredRecord] = []
    if raw.metadata.get("source_kind") in {"calendar_page", "calendar_pdf"} or "calendar" in raw.title.lower():
        for event in extract_calendar_events(raw):
            records.append(
                StructuredRecord(
                    record_id=stable_hash(f"calendar_event:{raw.parent_doc_id}:{event.event_name}"),
                    record_type="calendar_event",
                    parent_doc_id=raw.parent_doc_id,
                    source_url=raw.source_url,
                    title=event.event_name,
                    data=event.model_dump(),
                    metadata=raw.metadata,
                )
            )
    if raw.metadata.get("source_kind") == "financial_policy" or "financial" in raw.title.lower():
        records.extend(extract_fee_records(raw))
    if raw.metadata.get("source_kind") == "academic_catalog":
        records.extend(extract_program_records(raw))
    return _dedupe_records(records)


def extract_fee_records(raw: RawDocument) -> list[StructuredRecord]:
    records: list[StructuredRecord] = []
    for index, line in enumerate(raw.content.splitlines()):
        stripped = normalize_text(line)
        if not stripped:
            continue
        amount_match = VND_PATTERN.search(stripped)
        if not amount_match:
            continue
        amount_text = amount_match.group("amount").strip()
        currency = amount_match.group("currency").upper().replace("VNĐ", "VND")
        fee_name = stripped[: amount_match.start()].strip(" :-") or stripped
        data = {
            "fee_name": fee_name,
            "fee_type": infer_fee_type(stripped),
            "amount": normalize_amount(amount_text),
            "currency": currency,
            "amount_text_original": amount_match.group(0),
            "collection_time": infer_collection_time(stripped),
            "applies_to": None,
            "conditions": stripped,
            "row_index": index,
        }
        records.append(
            StructuredRecord(
                record_id=stable_hash(f"fee_record:{raw.parent_doc_id}:{index}:{stripped}"),
                record_type="fee_record",
                parent_doc_id=raw.parent_doc_id,
                source_url=raw.source_url,
                title=fee_name,
                data=data,
                metadata=raw.metadata,
            )
        )
    return records


def extract_program_records(raw: RawDocument) -> list[StructuredRecord]:
    records: list[StructuredRecord] = []
    current_college: str | None = None
    current_degree: str | None = None
    for line in raw.content.splitlines():
        stripped = normalize_text(line).lstrip("#").strip()
        if not stripped:
            continue
        if stripped.lower().startswith("college of"):
            current_college = stripped
        if any(prefix in stripped for prefix in ["Bachelor of", "Master of", "Ph.D.", "Medical Doctor"]):
            current_degree = "undergraduate" if "Bachelor" in stripped or "Medical Doctor" in stripped else "graduate"
            data = {
                "college": current_college,
                "degree_level": current_degree,
                "program_name": stripped,
                "major": stripped,
                "concentration": None,
                "minor": None,
                "cohort": infer_cohort(stripped),
            }
            records.append(
                StructuredRecord(
                    record_id=stable_hash(f"program:{raw.parent_doc_id}:{current_college}:{stripped}"),
                    record_type="program",
                    parent_doc_id=raw.parent_doc_id,
                    source_url=raw.source_url,
                    title=stripped,
                    data=data,
                    metadata=raw.metadata,
                )
            )
    return records


def link_records_from_links(
    links: list[LinkReference],
    parent_doc_id: str,
    metadata: dict[str, Any] | None = None,
) -> list[StructuredRecord]:
    metadata = metadata or {}
    records: list[StructuredRecord] = []
    for link in links:
        records.append(
            StructuredRecord(
                record_id=stable_hash(f"link_reference:{link.source_url}:{link.target_url}:{link.anchor_text}"),
                record_type="link_reference",
                parent_doc_id=parent_doc_id,
                source_url=link.source_url,
                title=link.anchor_text,
                data=link.model_dump(),
                metadata=metadata,
            )
        )
    return records


def normalize_date_range(date_text: str, academic_year: str | None = None) -> tuple[str | None, str | None]:
    normalized = date_text.replace("Sept", "Sep")
    parts = normalized.split("-")
    if not DATE_VALUE_PATTERN.search(normalized):
        return None, None

    years = _academic_year_bounds(academic_year)
    if len(parts) >= 3 and parts[1].isalpha():
        start = _date_token_to_iso(f"{parts[0]}-{parts[1]}", years)
        end = None
        if len(parts) >= 4:
            end = _date_token_to_iso(f"{parts[2]}-{parts[3]}", years)
        return start, end
    if len(parts) >= 2 and DATE_VALUE_PATTERN.search(parts[-1]):
        if len(parts) == 2:
            return _date_token_to_iso(normalized, years), None
        month = parts[-1]
        start = _date_token_to_iso(f"{parts[0]}-{month}", years)
        end = _date_token_to_iso(f"{parts[1]}-{month}", years)
        return start, end
    return _date_token_to_iso(normalized, years), None


def _date_token_to_iso(token: str, academic_year_bounds: tuple[int, int] | None) -> str | None:
    token = token.strip().replace(" ", "-")
    match = re.search(r"(?P<day>\d{1,2})[- ](?P<month>[A-Za-z]+)(?:[- ](?P<year>\d{2,4}))?", token)
    if not match:
        return None
    month = MONTHS.get(match.group("month").lower())
    if not month:
        return None
    year_text = match.group("year")
    if year_text:
        year = int(year_text)
        if year < 100:
            year += 2000
    elif academic_year_bounds:
        start_year, end_year = academic_year_bounds
        year = start_year if month >= 9 else end_year
    else:
        year = 2025 if month >= 9 else 2026
    return f"{year:04d}-{month:02d}-{int(match.group('day')):02d}"


def _academic_year_bounds(academic_year: str | None) -> tuple[int, int] | None:
    if not academic_year:
        return None
    years = re.findall(r"\d{4}", academic_year)
    if len(years) >= 2:
        return int(years[0]), int(years[1])
    return None


def infer_academic_year(text: str, url: str) -> str | None:
    match = re.search(r"(20\d{2})\s*[-/]\s*(20\d{2})", f"{text} {url}")
    if match:
        return f"{match.group(1)}-{match.group(2)}"
    if "2025" in text and "2026" in text:
        return "2025-2026"
    return None


def infer_event_type(text: str) -> str:
    lowered = text.lower()
    if "drop" in lowered:
        return "course_drop_deadline"
    if "add" in lowered or "transfer credit" in lowered:
        return "add_transfer_deadline"
    if "instruction begins" in lowered:
        return "instruction_begins"
    if "exam" in lowered:
        return "exam_period"
    if "holiday" in lowered or "tet" in lowered or "lunar" in lowered:
        return "holiday"
    if "registration" in lowered or "enrollment" in lowered:
        return "registration"
    return "academic_event"


def infer_fee_type(text: str) -> str:
    lowered = text.lower()
    if "tuition" in lowered:
        return "tuition"
    if "exam" in lowered:
        return "exam"
    if "library" in lowered or "document" in lowered or "equipment" in lowered:
        return "library"
    if "administrative" in lowered or "certified" in lowered or "student id" in lowered:
        return "academic_admin"
    return "fee"


def normalize_amount(value: str) -> int | None:
    digits = re.sub(r"\D", "", value)
    return int(digits) if digits else None


def infer_collection_time(text: str) -> str | None:
    lowered = text.lower()
    markers = ["at the time", "upon receipt", "within", "collected"]
    for marker in markers:
        index = lowered.find(marker)
        if index >= 0:
            return text[index:].strip()
    return None


def infer_cohort(text: str) -> str | None:
    match = re.search(r"(?:Cohort|AY)\s*([\d\s–-]+)", text, flags=re.IGNORECASE)
    return match.group(0) if match else None


def _extract_policy_code(row_text: str, title: str, dates: list[str]) -> str | None:
    text = row_text.replace(title, "", 1).strip()
    for date in dates:
        text = text.replace(date, " ")
    text = re.sub(r"\s+", " ", text).strip(" |:-")
    match = re.search(r"\b[A-Z0-9_./-]{2,}(?:-[A-Z0-9.]+)*\b", text)
    return match.group(0) if match else None


def _nearby_text(element) -> str:
    parent = element.find_parent(["tr", "li", "p", "div", "section"])
    if not parent:
        return normalize_text(element.get_text(" ", strip=True))
    return normalize_text(parent.get_text(" ", strip=True))


def _next_value(lines: list[str], start_index: int) -> str | None:
    for line in lines[start_index : start_index + 4]:
        if line and not line.endswith(":"):
            return line
    return None


def _listing_category_from_url(url: str) -> str:
    path = urlparse(url).path.strip("/")
    return path or "all-policies"


def _dedupe_records(records: list[StructuredRecord]) -> list[StructuredRecord]:
    seen: set[str] = set()
    deduped: list[StructuredRecord] = []
    for record in records:
        if record.record_id in seen:
            continue
        seen.add(record.record_id)
        deduped.append(record)
    return deduped
