from __future__ import annotations

import csv
import io
import mimetypes
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urldefrag, urljoin, urlparse

from bs4 import BeautifulSoup

from vinchatbot.app.ingest.normalizer import normalize_text
from vinchatbot.app.ingest.ocr import OcrResult, ocr_dependency_status
from vinchatbot.app.schemas.document import LinkReference, StructuredRecord, stable_hash

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tif", ".tiff", ".svg"}
SPREADSHEET_EXTENSIONS = {".xlsx", ".xls", ".csv"}
MARKDOWN_EXTENSIONS = {".md", ".markdown"}
DOWNLOAD_EXTENSIONS = (
    IMAGE_EXTENSIONS
    | SPREADSHEET_EXTENSIONS
    | MARKDOWN_EXTENSIONS
    | {".pdf", ".doc", ".docx", ".ppt", ".pptx", ".txt", ".zip"}
)
IMAGE_ATTRS = ("src", "data-src", "data-lazy-src", "data-original", "data-srcset", "srcset")


def extract_html_image_assets(
    content: str,
    source_url: str,
    metadata: dict[str, Any] | None = None,
    *,
    enable_ocr: bool = False,
    image_download_enabled: bool = False,
    ocr_engine: str = "paddleocr",
    ocr_model: str = "PP-OCRv5",
    ocr_lang: str = "en",
) -> list[StructuredRecord]:
    metadata = metadata or {}
    soup = BeautifulSoup(content, "html.parser")
    records: list[StructuredRecord] = []
    section_stack: list[str] = []
    parent_doc_id = stable_hash(metadata.get("canonical_url") or source_url)

    for element in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "img"]):
        if element.name and element.name.startswith("h"):
            level = int(element.name[1])
            heading = normalize_text(element.get_text(" ", strip=True))
            if heading:
                section_stack = section_stack[: level - 1]
                section_stack.append(heading)
            continue

        asset_url = _image_url_from_tag(element, source_url)
        if not asset_url:
            continue
        alt_text = normalize_text(str(element.get("alt") or ""))
        title_text = normalize_text(str(element.get("title") or ""))
        caption = _caption_for_image(element)
        nearby_text = _nearby_text(element, max_chars=360)
        width = _int_attr(element.get("width"))
        height = _int_attr(element.get("height"))
        filename = _filename_from_url(asset_url)
        mime_type = mimetypes.guess_type(asset_url)[0]
        description, description_source, confidence = describe_image_asset_from_context(
            filename=filename,
            section_path=section_stack,
            alt_text=alt_text,
            caption=caption,
            nearby_text=nearby_text,
        )
        ocr_status = _ocr_initial_status(
            enable_ocr=enable_ocr,
            image_download_enabled=image_download_enabled,
            ocr_engine=ocr_engine,
        )
        data = {
            "asset_url": asset_url,
            "asset_type": "image",
            "mime_type": mime_type,
            "filename": filename,
            "alt_text": alt_text or None,
            "title_text": title_text or None,
            "caption": caption or None,
            "nearby_text": nearby_text or None,
            "section_path": list(section_stack),
            "page_number": None,
            "width": width,
            "height": height,
            "file_size_bytes": None,
            "content_hash": stable_hash(asset_url),
            "description": description,
            "description_source": description_source,
            "description_confidence": confidence,
            "ocr_enabled": enable_ocr,
            "ocr_status": ocr_status,
            "ocr_text": None,
            "ocr_engine": ocr_engine if enable_ocr else None,
            "ocr_model": ocr_model if enable_ocr else None,
            "ocr_lang": ocr_lang if enable_ocr else None,
            "ocr_confidence": None,
        }
        records.append(
            StructuredRecord(
                record_id=stable_hash(f"image_asset:{source_url}:{asset_url}:{len(records)}"),
                record_type="image_asset",
                parent_doc_id=parent_doc_id,
                source_url=source_url,
                title=caption or alt_text or filename,
                data=data,
                metadata=metadata,
            )
        )
    return _dedupe_records(records)


def describe_image_asset_from_context(
    *,
    filename: str | None,
    section_path: list[str],
    alt_text: str | None,
    caption: str | None,
    nearby_text: str | None,
) -> tuple[str, str, float]:
    section = " > ".join(section_path[-2:]) if section_path else None
    parts: list[str] = []
    if section:
        parts.append(f"Image from section {section}.")
    if caption:
        parts.append(f"Caption: {caption}")
        return normalize_text(" ".join(parts)), "caption", 0.75
    if alt_text:
        parts.append(f"Alt text: {alt_text}")
        return normalize_text(" ".join(parts)), "alt", 0.65
    if nearby_text:
        parts.append(f"Nearby text: {nearby_text}")
        return normalize_text(" ".join(parts)), "context", 0.4
    if filename:
        parts.append(f"Filename: {filename}")
    return normalize_text(" ".join(parts) or "Image asset with no textual context."), "filename", 0.2


def extract_html_table_records(
    content: str,
    source_url: str,
    metadata: dict[str, Any] | None = None,
) -> list[StructuredRecord]:
    metadata = metadata or {}
    soup = BeautifulSoup(content, "html.parser")
    records: list[StructuredRecord] = []
    parent_doc_id = stable_hash(metadata.get("canonical_url") or source_url)
    for index, table in enumerate(soup.find_all("table"), start=1):
        rows = _table_rows(table)
        if not rows:
            continue
        caption = normalize_text(table.caption.get_text(" ", strip=True)) if table.caption else None
        section_path = _section_path_before(table)
        headers, data_rows = _headers_and_data_rows(table, rows)
        table_id = stable_hash(f"table:{source_url}:{index}:{caption or rows[0]}")
        rag_text = table_record_to_text(
            title=caption or metadata.get("document_title") or source_url,
            headers=headers,
            rows=data_rows,
        )
        data = {
            "table_id": table_id,
            "caption": caption,
            "headers": headers,
            "rows": data_rows,
            "row_count": len(data_rows),
            "column_count": len(headers),
            "section_path": section_path,
            "page_number": None,
            "rag_text": rag_text,
            "content_hash": stable_hash(rag_text),
        }
        records.append(
            StructuredRecord(
                record_id=stable_hash(f"table_record:{table_id}"),
                record_type="table_record",
                parent_doc_id=parent_doc_id,
                source_url=source_url,
                title=caption or metadata.get("document_title"),
                data=data,
                metadata=metadata,
            )
        )
    return records


def table_record_to_text(
    *,
    title: str,
    headers: list[str],
    rows: list[list[str]],
    max_rows: int = 30,
) -> str:
    lines = [f"Table: {normalize_text(title)}"]
    if headers:
        lines.append(f"Columns: {' | '.join(headers)}")
    for index, row in enumerate(rows[:max_rows], start=1):
        if headers and len(headers) == len(row):
            row_text = " | ".join(f"{header}: {value}" for header, value in zip(headers, row, strict=False))
        else:
            row_text = " | ".join(row)
        lines.append(f"Row {index}: {row_text}")
    return normalize_text("\n".join(lines))


def file_asset_records_from_links(
    links: list[LinkReference],
    parent_doc_id: str,
    metadata: dict[str, Any] | None = None,
) -> list[StructuredRecord]:
    metadata = metadata or {}
    records: list[StructuredRecord] = []
    for link in links:
        extension = Path(urlparse(link.target_url).path).suffix.lower()
        if extension not in DOWNLOAD_EXTENSIONS:
            continue
        mime_type = mimetypes.guess_type(link.target_url)[0]
        asset_type = _asset_type_from_extension(extension, mime_type)
        data = {
            "asset_url": link.target_url,
            "asset_type": asset_type,
            "mime_type": mime_type,
            "filename": _filename_from_url(link.target_url),
            "anchor_text": link.anchor_text,
            "link_context": link.link_context,
            "section_path": link.section_path,
            "file_size_bytes": None,
            "content_hash": stable_hash(link.target_url),
            "should_crawl": link.should_crawl,
            "requires_login": link.requires_login,
            "source_trust": link.source_trust,
        }
        records.append(
            StructuredRecord(
                record_id=stable_hash(f"file_asset:{link.source_url}:{link.target_url}:{link.anchor_text}"),
                record_type="file_asset",
                parent_doc_id=parent_doc_id,
                source_url=link.source_url,
                title=link.anchor_text or data["filename"],
                data=data,
                metadata=metadata,
            )
        )
    return _dedupe_records(records)


def build_binary_image_asset_record(
    *,
    source_url: str,
    parent_doc_id: str,
    metadata: dict[str, Any],
    content: bytes,
    mime_type: str | None,
    enable_ocr: bool,
    ocr_engine: str,
    ocr_model: str,
    ocr_lang: str,
    ocr_result: OcrResult | None = None,
    ocr_status: str | None = None,
) -> StructuredRecord:
    filename = _filename_from_url(source_url)
    description, description_source, confidence = describe_image_asset_from_context(
        filename=filename,
        section_path=list(metadata.get("section_path", [])),
        alt_text=None,
        caption=None,
        nearby_text=metadata.get("link_context"),
    )
    data = {
        "asset_url": source_url,
        "asset_type": "image",
        "mime_type": mime_type,
        "filename": filename,
        "alt_text": None,
        "caption": None,
        "nearby_text": metadata.get("link_context"),
        "section_path": list(metadata.get("section_path", [])),
        "page_number": None,
        "width": None,
        "height": None,
        "file_size_bytes": len(content),
        "content_hash": stable_hash(content.hex()),
        "description": description,
        "description_source": description_source,
        "description_confidence": confidence,
        "ocr_enabled": enable_ocr,
        "ocr_status": ocr_status or ("completed" if ocr_result else _ocr_initial_status(enable_ocr, True, ocr_engine)),
        "ocr_text": ocr_result.text if ocr_result else None,
        "ocr_engine": ocr_engine if enable_ocr else None,
        "ocr_model": ocr_model if enable_ocr else None,
        "ocr_lang": ocr_lang if enable_ocr else None,
        "ocr_confidence": ocr_result.confidence if ocr_result else None,
    }
    return StructuredRecord(
        record_id=stable_hash(f"image_asset:{source_url}:{data['content_hash']}"),
        record_type="image_asset",
        parent_doc_id=parent_doc_id,
        source_url=source_url,
        title=filename,
        data=data,
        metadata=metadata,
    )


def build_file_asset_record(
    *,
    source_url: str,
    parent_doc_id: str,
    metadata: dict[str, Any],
    content: bytes,
    mime_type: str | None,
) -> StructuredRecord:
    filename = _filename_from_url(source_url)
    data = {
        "asset_url": source_url,
        "asset_type": _asset_type_from_extension(Path(urlparse(source_url).path).suffix.lower(), mime_type),
        "mime_type": mime_type,
        "filename": filename,
        "file_size_bytes": len(content),
        "content_hash": stable_hash(content.hex()),
        "source_trust": metadata.get("source_trust"),
    }
    return StructuredRecord(
        record_id=stable_hash(f"file_asset:{source_url}:{data['content_hash']}"),
        record_type="file_asset",
        parent_doc_id=parent_doc_id,
        source_url=source_url,
        title=filename,
        data=data,
        metadata=metadata,
    )


def extract_pdf_page_image_assets(
    *,
    page_stats: list[dict[str, Any]],
    source_url: str,
    parent_doc_id: str,
    metadata: dict[str, Any],
    enable_ocr: bool,
    ocr_engine: str,
    ocr_model: str,
    ocr_lang: str,
    ocr_min_text_chars_per_page: int,
    ocr_max_pdf_pages: int,
    ocr_results: dict[int, OcrResult] | None = None,
    ocr_status_by_page: dict[int, str] | None = None,
) -> list[StructuredRecord]:
    records: list[StructuredRecord] = []
    ocr_results = ocr_results or {}
    ocr_status_by_page = ocr_status_by_page or {}
    for stat in page_stats:
        page_number = int(stat["page_number"])
        text_char_count = int(stat.get("text_char_count") or 0)
        image_count = int(stat.get("embedded_image_count") or 0)
        needs_ocr = text_char_count < ocr_min_text_chars_per_page
        if not needs_ocr and image_count <= 0:
            continue
        result = ocr_results.get(page_number)
        ocr_status = ocr_status_by_page.get(page_number)
        if not ocr_status:
            if not enable_ocr:
                ocr_status = "disabled"
            elif page_number > ocr_max_pdf_pages:
                ocr_status = "skipped_page_cap"
            else:
                ocr_status = "completed" if result else "skipped_no_text"
        data = {
            "asset_url": f"{source_url}#page={page_number}",
            "asset_type": "pdf_page_image",
            "mime_type": "image/png",
            "filename": f"{_filename_from_url(source_url)}#page={page_number}",
            "alt_text": None,
            "caption": None,
            "nearby_text": None,
            "section_path": list(metadata.get("section_path", [])),
            "page_number": page_number,
            "width": stat.get("width"),
            "height": stat.get("height"),
            "file_size_bytes": None,
            "content_hash": stable_hash(f"{source_url}:{page_number}:{text_char_count}:{image_count}"),
            "description": f"PDF page image candidate from page {page_number}.",
            "description_source": "page_context",
            "description_confidence": 0.3,
            "needs_ocr": needs_ocr,
            "text_char_count": text_char_count,
            "embedded_image_count": image_count,
            "ocr_enabled": enable_ocr,
            "ocr_status": ocr_status,
            "ocr_text": result.text if result else None,
            "ocr_engine": ocr_engine if enable_ocr else None,
            "ocr_model": ocr_model if enable_ocr else None,
            "ocr_lang": ocr_lang if enable_ocr else None,
            "ocr_confidence": result.confidence if result else None,
        }
        records.append(
            StructuredRecord(
                record_id=stable_hash(f"pdf_page_image:{source_url}:{page_number}"),
                record_type="image_asset",
                parent_doc_id=parent_doc_id,
                source_url=source_url,
                title=f"Page {page_number}",
                data=data,
                metadata=metadata,
            )
        )
        if result and result.text:
            records.append(
                build_ocr_text_record(
                    source_url=source_url,
                    parent_doc_id=parent_doc_id,
                    metadata=metadata,
                    asset_url=f"{source_url}#page={page_number}",
                    page_number=page_number,
                    result=result,
                    ocr_engine=ocr_engine,
                    ocr_model=ocr_model,
                    ocr_lang=ocr_lang,
                )
            )
    return records


def build_ocr_text_record(
    *,
    source_url: str,
    parent_doc_id: str,
    metadata: dict[str, Any],
    asset_url: str,
    page_number: int | None,
    result: OcrResult,
    ocr_engine: str,
    ocr_model: str,
    ocr_lang: str,
) -> StructuredRecord:
    data = {
        "asset_url": asset_url,
        "ocr_text": result.text,
        "ocr_engine": ocr_engine,
        "ocr_model": ocr_model,
        "ocr_lang": ocr_lang,
        "ocr_confidence": result.confidence,
        "page_number": page_number,
        "bbox_count": result.bbox_count,
        "boxes": result.boxes,
        "content_hash": stable_hash(result.text),
    }
    return StructuredRecord(
        record_id=stable_hash(f"ocr_text:{asset_url}:{stable_hash(result.text)}"),
        record_type="ocr_text",
        parent_doc_id=parent_doc_id,
        source_url=source_url,
        title=f"OCR page {page_number}" if page_number else "OCR text",
        data=data,
        metadata=metadata,
    )


def parse_csv_records(
    content: bytes | str,
    source_url: str,
    metadata: dict[str, Any],
) -> tuple[str, list[StructuredRecord]]:
    text = content.decode("utf-8-sig", errors="replace") if isinstance(content, bytes) else content
    rows = list(csv.reader(io.StringIO(text)))
    if not rows:
        return "", []
    headers = [normalize_text(value) for value in rows[0]]
    data_rows = [[normalize_text(value) for value in row] for row in rows[1:] if any(value.strip() for value in row)]
    parent_doc_id = stable_hash(metadata.get("canonical_url") or source_url)
    records: list[StructuredRecord] = []
    lines = [f"CSV: {metadata.get('document_title') or source_url}", f"Columns: {' | '.join(headers)}"]
    for row_index, row in enumerate(data_rows, start=1):
        row_data = _row_dict(headers, row)
        row_text = _spreadsheet_row_to_text(row_index, headers, row)
        lines.append(row_text)
        records.append(
            StructuredRecord(
                record_id=stable_hash(f"spreadsheet_row:{source_url}:{row_index}:{row_text}"),
                record_type="spreadsheet_row",
                parent_doc_id=parent_doc_id,
                source_url=source_url,
                title=f"Row {row_index}",
                data={
                    "sheet_name": "csv",
                    "row_index": row_index,
                    "headers": headers,
                    "values": row_data,
                    "rag_text": row_text,
                    "content_hash": stable_hash(row_text),
                },
                metadata=metadata,
            )
        )
    return normalize_text("\n".join(lines)), records


def is_download_asset_url(url: str) -> bool:
    return Path(urlparse(url).path).suffix.lower() in DOWNLOAD_EXTENSIONS


def is_image_url(url: str, mime_type: str | None = None) -> bool:
    return Path(urlparse(url).path).suffix.lower() in IMAGE_EXTENSIONS or (mime_type or "").startswith("image/")


def is_spreadsheet_url(url: str, mime_type: str | None = None) -> bool:
    extension = Path(urlparse(url).path).suffix.lower()
    haystack = f"{url} {mime_type or ''}".lower()
    return extension in SPREADSHEET_EXTENSIONS or "spreadsheet" in haystack or "excel" in haystack


def is_markdown_url(url: str, mime_type: str | None = None) -> bool:
    extension = Path(urlparse(url).path).suffix.lower()
    haystack = f"{url} {mime_type or ''}".lower()
    return extension in MARKDOWN_EXTENSIONS or "text/markdown" in haystack or "text/x-markdown" in haystack


def _image_url_from_tag(element, source_url: str) -> str | None:
    for attr in IMAGE_ATTRS:
        value = element.get(attr)
        if not value:
            continue
        if attr.endswith("srcset"):
            value = _best_srcset_candidate(str(value))
        if value:
            url, _ = urldefrag(urljoin(source_url, str(value).strip()))
            if url.startswith("data:"):
                return None
            return url
    parent_picture = element.find_parent("picture")
    if parent_picture:
        source = parent_picture.find("source")
        if source:
            value = source.get("srcset") or source.get("data-srcset") or source.get("src")
            if value:
                candidate = _best_srcset_candidate(str(value))
                url, _ = urldefrag(urljoin(source_url, candidate))
                return url
    return None


def _best_srcset_candidate(srcset: str) -> str:
    candidates = [item.strip().split(" ", 1)[0] for item in srcset.split(",") if item.strip()]
    return candidates[-1] if candidates else ""


def _caption_for_image(element) -> str | None:
    figure = element.find_parent("figure")
    if figure:
        caption = figure.find("figcaption")
        if caption:
            return normalize_text(caption.get_text(" ", strip=True)) or None
    parent = element.find_parent(["div", "li", "section"])
    if not parent:
        return None
    for selector in [".caption", ".wp-caption-text", ".elementor-image-caption"]:
        candidate = parent.select_one(selector)
        if candidate:
            text = normalize_text(candidate.get_text(" ", strip=True))
            if text:
                return text
    return None


def _nearby_text(element, max_chars: int = 260) -> str | None:
    parent = element.find_parent(["figure", "li", "p", "div", "section", "article"])
    if not parent:
        return None
    text = normalize_text(parent.get_text(" ", strip=True))
    if not text:
        return None
    return text[:max_chars].strip()


def _section_path_before(element) -> list[str]:
    headings = []
    for heading in element.find_all_previous(["h1", "h2", "h3", "h4", "h5", "h6"]):
        text = normalize_text(heading.get_text(" ", strip=True))
        if not text:
            continue
        headings.append((int(heading.name[1]), text))
    section_stack: list[str] = []
    for level, text in reversed(headings):
        section_stack = section_stack[: level - 1]
        section_stack.append(text)
    return section_stack


def _table_rows(table) -> list[list[str]]:
    rows: list[list[str]] = []
    for tr in table.find_all("tr"):
        cells = [
            normalize_text(cell.get_text(" ", strip=True))
            for cell in tr.find_all(["th", "td"])
        ]
        if any(cells):
            rows.append(cells)
    return rows


def _headers_and_data_rows(table, rows: list[list[str]]) -> tuple[list[str], list[list[str]]]:
    first_tr = table.find("tr")
    has_header = bool(first_tr and first_tr.find_all("th"))
    if has_header:
        headers = rows[0]
        data_rows = rows[1:]
    else:
        column_count = max(len(row) for row in rows)
        headers = [f"Column {index}" for index in range(1, column_count + 1)]
        data_rows = rows
    normalized_rows = [row + [""] * (len(headers) - len(row)) for row in data_rows]
    return headers, normalized_rows


def _row_dict(headers: list[str], row: list[str]) -> dict[str, str]:
    return {
        header or f"column_{index + 1}": row[index] if index < len(row) else ""
        for index, header in enumerate(headers)
    }


def _spreadsheet_row_to_text(row_index: int, headers: list[str], row: list[str]) -> str:
    row_values = _row_dict(headers, row)
    return f"Row {row_index}: " + " | ".join(
        f"{key}: {value}" for key, value in row_values.items() if value
    )


def _filename_from_url(url: str) -> str:
    path = unquote(urlparse(url).path)
    return Path(path).name or "asset"


def _int_attr(value: Any) -> int | None:
    try:
        return int(str(value).replace("px", "").strip())
    except (TypeError, ValueError):
        return None


def _ocr_initial_status(
    enable_ocr: bool,
    image_download_enabled: bool,
    ocr_engine: str,
) -> str:
    if not enable_ocr:
        return "disabled"
    available, reason = ocr_dependency_status(ocr_engine)
    if not available:
        return reason or "skipped_dependency_missing"
    if not image_download_enabled:
        return "skipped_download_disabled"
    return "pending"


def _asset_type_from_extension(extension: str, mime_type: str | None) -> str:
    if extension in IMAGE_EXTENSIONS or (mime_type or "").startswith("image/"):
        return "image"
    if extension == ".pdf" or mime_type == "application/pdf":
        return "pdf"
    if extension in SPREADSHEET_EXTENSIONS:
        return "spreadsheet"
    if extension in MARKDOWN_EXTENSIONS:
        return "markdown"
    return "file"


def _dedupe_records(records: list[StructuredRecord]) -> list[StructuredRecord]:
    seen: set[str] = set()
    deduped: list[StructuredRecord] = []
    for record in records:
        if record.record_id in seen:
            continue
        seen.add(record.record_id)
        deduped.append(record)
    return deduped
