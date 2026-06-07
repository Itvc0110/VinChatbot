from __future__ import annotations

import re
import unicodedata
from urllib.parse import urlparse

VIETNAMESE_MARKERS = {
    "đ",
    "ă",
    "â",
    "ê",
    "ô",
    "ơ",
    "ư",
    "á",
    "à",
    "ả",
    "ã",
    "ạ",
    "é",
    "è",
    "ẻ",
    "ẽ",
    "ẹ",
    "í",
    "ì",
    "ỉ",
    "ĩ",
    "ị",
    "ó",
    "ò",
    "ỏ",
    "õ",
    "ọ",
    "ú",
    "ù",
    "ủ",
    "ũ",
    "ụ",
    "ý",
    "ỳ",
    "ỷ",
    "ỹ",
    "ỵ",
}


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    text = text.replace("\x00", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def guess_language(text: str) -> str:
    lowered = text.lower()
    marker_count = sum(lowered.count(marker) for marker in VIETNAMESE_MARKERS)
    if marker_count >= 3:
        return "vi"
    return "en"


def infer_category(url: str, title: str) -> tuple[str, str]:
    haystack = f"{url} {title}".lower()
    if "calendar" in haystack or "academic-calendar" in haystack:
        return "academic", "calendar"
    if "academic-catalog" in haystack or "program-specification" in haystack:
        return "academic", "catalog"
    if "financial" in haystack or "tariff" in haystack or "tuition" in haystack:
        return "student_affairs", "financial"
    if "code-of-conduct" in haystack or "conduct" in haystack:
        return "student_affairs", "conduct"
    if "registrar" in haystack:
        return "academic", "registrar"
    if "library" in haystack:
        return "student_services", "library"
    if "student-affairs" in haystack or "policy" in haystack:
        return "student_affairs", "policy"
    return "general", "unknown"


def classify_domain(url: str) -> tuple[str, str, str]:
    host = urlparse(url).netloc.lower()
    if host == "policy.vinuni.edu.vn":
        return host, "policy", "official_high"
    if host == "vinuni.edu.vn" or host.endswith(".vinuni.edu.vn"):
        return host, "vinuni_subdomain", "official"
    if host.endswith("vinuni.edu.vn"):
        return host, "vinuni_owned", "official"
    return host or "unknown", "external", "external_low"


def infer_source_kind(url: str, content_type: str | None = None, title: str | None = None) -> str:
    haystack = f"{url} {content_type or ''} {title or ''}".lower()
    host = urlparse(url).netloc.lower()
    path = urlparse(url).path.lower()
    if _is_image_path(path) or (content_type or "").lower().startswith("image/"):
        return "image_asset"
    if path.endswith((".xlsx", ".xls")) or "spreadsheet" in haystack or "excel" in haystack:
        return "spreadsheet"
    if path.endswith(".csv") or "text/csv" in haystack:
        return "csv"
    if path.endswith(".md") or "text/markdown" in haystack or "text/x-markdown" in haystack:
        return "markdown"
    if "student-gateway" in path:
        return "gateway_page"
    if "academic-calendar" in path and "pdf" not in haystack:
        return "calendar_page"
    if path.endswith(".pdf") and "calendar" in haystack:
        return "calendar_pdf"
    if "pdf" in haystack:
        return "policy_pdf" if host == "policy.vinuni.edu.vn" else "external_public_page"
    if host == "policy.vinuni.edu.vn" and _is_policy_listing_path(path):
        return "policy_listing"
    if host == "policy.vinuni.edu.vn" and "/publication/academic-catalogs" in path:
        return "academic_catalog"
    if host == "policy.vinuni.edu.vn" and "/all-policies/" in path:
        if "financial" in haystack or "tariff" in haystack:
            return "financial_policy"
        return "policy_html"
    if host == "registrar.vinuni.edu.vn":
        return "registrar_page"
    if host == "library.vinuni.edu.vn":
        return "library_page"
    if host.endswith("vinuni.edu.vn") or host == "vinuni.edu.vn":
        return "external_public_page"
    return "external_public_page"


def _is_image_path(path: str) -> bool:
    return path.endswith((".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tif", ".tiff", ".svg"))


def _is_policy_listing_path(path: str) -> bool:
    listing_paths = {
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
    normalized = path if path.endswith("/") else f"{path}/"
    return normalized in listing_paths
