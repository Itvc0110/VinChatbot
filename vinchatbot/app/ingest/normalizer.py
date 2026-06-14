from __future__ import annotations

import re
import unicodedata
from collections import Counter
from urllib.parse import urlparse

_BOILERPLATE_LINES = {
    "policy content",
    "policy status",
    "pdf version",
    "table of contents",
    "event calendar",
}
_BOILERPLATE_PREFIXES = ("access this link to read the full document",)


def strip_boilerplate(text: str) -> str:
    """Remove known boilerplate lines and repeated nav/menu lines.

    Drops policy-page scaffolding ("Policy Content", "PDF version", ...), collapses
    consecutive duplicate lines, and removes lines that repeat many times across the page
    (navigation menus) after their first occurrence — the main driver of nav-heavy pages
    over-chunking.
    """
    lines = text.split("\n")
    counts = Counter(line.strip().lower() for line in lines if line.strip())
    out: list[str] = []
    prev_low: str | None = None
    emitted: set[str] = set()
    for line in lines:
        low = line.strip().lower()
        bare = low.lstrip("-*•#").strip()  # tolerate Markdown list/heading prefixes
        if bare in _BOILERPLATE_LINES:
            continue
        if any(bare.startswith(prefix) for prefix in _BOILERPLATE_PREFIXES):
            continue
        if low and low == prev_low:
            continue
        if low and counts[low] > 3 and low in emitted:
            continue
        out.append(line)
        if low:
            emitted.add(low)
            prev_low = low
    return "\n".join(out)

VIETNAMESE_MARKERS = set(
    "ăâđêôơư"
    "áàảãạắằẳẵặấầẩẫậéèẻẽẹếềểễệ"
    "íìỉĩịóòỏõọốồổỗộớờởỡợ"
    "úùủũụứừửữựýỳỷỹỵ"
)

ENGLISH_HINTS = {
    "academic",
    "calendar",
    "course",
    "deadline",
    "drop",
    "fee",
    "policy",
    "student",
    "tuition",
}


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    text = text.replace("\x00", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def guess_language(text: str) -> str:
    lowered = text.lower()
    marker_count = sum(1 for char in lowered if char in VIETNAMESE_MARKERS)
    has_vietnamese = marker_count >= 2 or "việt" in lowered or "sinh viên" in lowered
    english_hint_count = sum(1 for term in ENGLISH_HINTS if re.search(rf"\b{term}\b", lowered))
    if has_vietnamese and english_hint_count >= 2:
        return "mixed"
    if has_vietnamese:
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
    # Conduct/discipline cluster. "conduct" also matches "misconduct"; the extra terms catch
    # the disciplinary appendices and the Vietnamese student-affairs regulation (VU_CTSV02,
    # "quy che cong tac sinh vien") whose titles/URLs omit the word "conduct" — keeping the
    # whole Student Code of Conduct family under one subcategory for routing/boosts.
    if (
        "code-of-conduct" in haystack
        or "conduct" in haystack
        or "disciplinary" in haystack
        or "violation" in haystack
        or "student-behaviour" in haystack
        or "student behaviour" in haystack
        or "cong-tac-sinh-vien" in haystack
        or "cong tac sinh vien" in haystack
    ):
        return "student_affairs", "conduct"
    if "registrar" in haystack:
        return "academic", "registrar"
    if "library" in haystack:
        return "student_services", "library"
    if "experience" in haystack:
        return "student_services", "student_life"
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
    if path.endswith(".docx") or "wordprocessingml" in haystack or "msword" in haystack:
        return "docx"
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
    if host == "experience.vinuni.edu.vn":
        return "student_life_page"
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
