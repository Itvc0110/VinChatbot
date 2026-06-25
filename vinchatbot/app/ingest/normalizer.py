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
    # Expansion content (placed last so existing assignments are unchanged).
    if "admission" in haystack or "tuyen-sinh" in haystack:
        return "student_services", "admissions"
    if "scholarship" in haystack or "hoc-bong" in haystack:
        return "student_affairs", "financial"
    if "/undergraduate" in haystack or "/graduate" in haystack or "curriculum" in haystack:
        return "academic", "program"
    # Main-domain reference sections (people/leadership bios, exchange, student life).
    if "/people/" in url:
        return "general", "people"
    if "/global_exchange/" in url or "/student_life/" in url:
        return "student_services", "student_life"
    if "/academics/" in url:
        return "academic", "program"
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


# Expansion subdomains (admissions/scholarships/4 colleges) are heavily mixed with news/events/marketing —
# their pages are kept ONLY on student/admissions/program paths; everything else falls to external_public_page
# (dropped by --student-only). Markers cover EN + VI.
EXPANSION_HOSTS = {
    "admissions.vinuni.edu.vn",
    "scholarships.vinuni.edu.vn",
    "cecs.vinuni.edu.vn",
    "chs.vinuni.edu.vn",
    "cbm.vinuni.edu.vn",
    "cas.vinuni.edu.vn",
}
# Section prefixes marking a student/admissions/program REFERENCE page. We match the FIRST path segment
# (a leading /vi//en/ language segment is skipped), NOT a substring anywhere: news posts are top-level
# descriptive slugs that are keyword-rich (e.g. /nursing-program-orientation-event-2021/) but do NOT sit
# under a section, whereas reference pages do (/undergraduate/, /faq-for-admissions/, /tuition-fee/,
# /graduate-programs/, /master-of-…). Substring matching let the news through; first-segment matching drops it.
_SECTION_PREFIXES = (
    "undergraduate", "graduate", "postgraduate", "master", "bachelor", "phd", "doctoral",
    "faq", "tuition", "fee", "scholarship", "financial", "apply", "admission", "requirement",
    "program", "curriculum", "major", "deadline",
    "dai-hoc", "sau-dai-hoc", "thac-si", "tien-si", "hoc-phi", "hoc-bong", "tuyen-sinh",
    "chuong-trinh", "nganh", "nop-don", "yeu-cau",
    # College program/section slugs the first-segment gate previously missed (audit 2026-06-24):
    # "bac-dai-hoc" (VI undergraduate — does NOT start with "dai-hoc"), the CHS MD program, and the
    # CECS undergraduate-research-opportunities program (uropcecs / uropcecs-2 → "urop").
    "bac-dai-hoc", "medical-doctor", "urop",
)


def is_high_value_expansion_path(url: str) -> bool:
    """True only for student/admissions/program REFERENCE pages on the expansion sites. Matches the FIRST
    path segment against a section prefix (skipping a leading /vi//en/ language segment). Top-level
    descriptive news slugs — keyword-rich but not under a section — are excluded."""
    return _first_segment(url) is not None and any(
        _first_segment(url).startswith(prefix) for prefix in _SECTION_PREFIXES
    )


def _first_segment(url_or_path: str) -> str | None:
    """First meaningful path segment, skipping a leading /vi//en/ language segment. None if path is empty."""
    path = url_or_path if url_or_path.startswith("/") else urlparse(url_or_path).path
    segs = [s for s in path.lower().split("/") if s]
    if segs and segs[0] in ("vi", "en") and len(segs) > 1:
        segs = segs[1:]
    return segs[0] if segs else None


# High-value SECTIONS on the main vinuni.edu.vn marketing domain → the kind --student-only keeps. The main
# domain is official (classify_domain → "official") but is mostly news/marketing, so it default-drops to
# external_public_page; these sections are the reference content under it that must NOT be dropped (audit
# 2026-06-24 — the President/leadership bug came from /people/ landing here and being filtered out). Anything
# NOT in this map (news slugs, /category//tag//event//job//research//wp-content/, …) stays external_public_page.
_MAINSITE_KEEP_SECTIONS = {
    "people": "profile_page",          # faculty, leadership, board, staff bios (incl. President/Provost)
    "academics": "program_page",       # academics landing / program overviews
    "global_exchange": "student_life_page",  # student exchange / study-abroad partners
    "student_life": "student_life_page",
    "about": "about_page",
    "about-us": "about_page",
    "leadership": "about_page",
    "governance": "about_page",
}


def _mainsite_kind(path: str) -> str:
    """Classify a page on the main vinuni.edu.vn domain by its first path section. Reference sections
    (people/academics/student-life/about/…) get a kept kind; everything else → external_public_page."""
    return _MAINSITE_KEEP_SECTIONS.get(_first_segment(path) or "", "external_public_page")


# PDF filename markers (audit 2026-06-24): the old rule kept PDFs ONLY on policy.vinuni, silently dropping
# official forms/guides/curricula on registrar/experience/college/admissions hosts (FRM* petition forms,
# STUDENT-GUIDE handbooks, Bachelor-of-Nursing CurriculumFramework, PhD admission notices). Marketing PDFs
# (posters/flyers/conference slides/partner one-pagers) must still drop.
_MARKETING_PDF_MARKERS = ("poster", "flyer", "banner", "brochure")
_REFERENCE_PDF_MARKERS = (
    "guide", "handbook", "guideline", "curriculum", "framework", "program", "regulation", "policy",
    "form", "frm", "petition", "tuition", "fee", "scholarship", "admission", "student", "manual",
    "catalog", "cohort", "mba", "msn", "bachelor", "master", "nursing", "workstudy",
    "quy-dinh", "quy-che", "huong-dan", "hoc-phi", "hoc-bong", "tuyen-sinh", "bieu-mau", "so-tay",
    "chuong-trinh", "thong-bao",
)


def _pdf_kind(host: str, path: str) -> str:
    """Classify a PDF on a VinUni host. Official student-service hosts (policy/registrar/experience/library)
    keep ALL their PDFs (forms, guides, handbooks, regulations — no marketing there). On admissions/college
    sites keep document-like PDFs and drop marketing by filename; on the main domain keep only PDFs whose
    filename looks like a document (it is otherwise conference slides / partner one-pagers)."""
    if host == "policy.vinuni.edu.vn":
        return "policy_pdf"
    if host == "registrar.vinuni.edu.vn":
        return "registrar_page"
    if host == "experience.vinuni.edu.vn":
        return "student_life_page"
    if host == "library.vinuni.edu.vn":
        return "library_page"
    name = path.rsplit("/", 1)[-1]
    if any(marker in name for marker in _MARKETING_PDF_MARKERS):
        return "external_public_page"
    if host == "admissions.vinuni.edu.vn":
        return "admissions_page"
    if host in EXPANSION_HOSTS:
        return "program_page"  # college PDFs: curricula / guides / notices
    if host.endswith("vinuni.edu.vn"):
        return "program_page" if any(m in name for m in _REFERENCE_PDF_MARKERS) else "external_public_page"
    return "external_public_page"


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
    # PDFs handled here (before the expansion path-gate and the host handlers) so a real document under a
    # /wp-content/ or non-reference path on ANY VinUni host is not mis-dropped. See _pdf_kind.
    if path.endswith(".pdf"):
        return _pdf_kind(host, path)
    # Expansion subdomains (classified BEFORE the generic pdf/fallthrough so their pages/PDFs get a high-value
    # kind --student-only keeps). PATH-GATED: these sites are marketing-heavy, so non-student/admissions/
    # program paths (news, events, /page/ pagination, /vi/ news…) fall to external_public_page → dropped.
    if host in EXPANSION_HOSTS:
        # College faculty/leadership bios live under /people/ on the college sites too — keep them.
        if _first_segment(path) == "people":
            return "profile_page"
        # Scholarships is a small dedicated site → keep broadly (its slugs often omit a marker word).
        if host == "scholarships.vinuni.edu.vn":
            return "scholarship_page"
        # Admissions + the marketing-heavy college sites: keep only student/admissions/program paths.
        if not is_high_value_expansion_path(url):
            return "external_public_page"
        if host == "admissions.vinuni.edu.vn":
            return "faq_page" if ("faq" in path or "commonly-asked" in path) else "admissions_page"
        return "program_page"  # the four colleges
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
    # Main vinuni.edu.vn marketing domain: official but news-heavy → keep only the reference sections
    # (people/academics/student-life/about/…); everything else default-drops to external_public_page.
    if host in ("vinuni.edu.vn", "www.vinuni.edu.vn"):
        return _mainsite_kind(path)
    if host.endswith("vinuni.edu.vn"):
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
