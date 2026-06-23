"""Deterministic policy doc selection (Phase 1.21).

VI policy questions undermatch their canonical all-policies detail page: a few large governance "magnet"
PDFs (VU_TS03 tariff, VU_HT03 academic regs), the page's own PDF twin, and on-topic non-policy pages
out-rank it after the multilingual rerank (the reranker's same-language bias). A retrieval probe confirmed
the canonical page IS in the pool for every magnet case — it is a *ranking*, not a recall, problem — and
the score gaps vary too much for any fixed boost factor to fix (rank 4 → rank 9, out of the top-8 context).

So instead of nudging scores, we SELECT the right document deterministically: when a policy question
confidently names one of the curated student-facing topics, the caller (`tools._search`) fetches that
canonical page by `source_url` and pins it to the front of the context — gap-proof.

Mirrors `structured_lookup`'s design: curated bilingual keywords, a SINGLE-WINNER rule (exactly one topic
must match — 0 or >1 ⇒ MISS), and fail-open (a MISS leaves the vector path byte-identical). Pure dict/regex,
no LLM/network, so it strictly reduces nondeterminism on the turns it handles.
"""

from __future__ import annotations

import json
from pathlib import Path

from vinchatbot.app.core.config import Settings, get_settings
from vinchatbot.app.rag.context import _fold, _salient_terms

POLICY_BASE_URL = "https://policy.vinuni.edu.vn/all-policies/"

# slug -> distinctive bilingual keyword phrases (written ACCENT-FREE; the query is folded before matching,
# so Vietnamese diacritics and đ are handled). Keep keywords DISTINCTIVE: a generic word shared across
# topics breaks the single-winner rule and the topic falls open (safe, but unhelpful). Order irrelevant.
POLICY_TOPICS: dict[str, tuple[str, ...]] = {
    "student-academic-integrity": (
        "academic integrity", "liem chinh hoc thuat", "liem chinh", "plagiarism", "dao van",
        "academic dishonesty", "gian lan hoc thuat",
    ),
    "student-affairs-regulations-code-of-conduct": (
        "code of conduct", "quy tac ung xu", "bo quy tac", "student conduct", "ky luat sinh vien",
    ),
    "attendance-policy-at-medical-doctor-program": (
        "md program", "chuong trinh md", "medical doctor program", "board of examiners", "hoi dong khao thi",
    ),
    "sexual-misconduct-and-response": (
        "sexual misconduct", "sexual harassment", "tinh duc", "quay roi", "xam hai",
    ),
    "guidelines-for-student-financial-support-request": (
        "financial aid", "financial support", "ho tro tai chinh", "tro cap tai chinh",
    ),
    "internship-management-policy": (
        "internship", "thuc tap",
    ),
    "library-policies-for-users": (
        "library", "thu vien", "muon sach", "muon tai lieu",
    ),
    "residential-life-guideline": (
        "residential", "dormitory", "ky tuc xa", "curfew", "gioi nghiem", "noi tru",
    ),
    "study-visa-guidelines-for-international-students": (
        "study visa", "visa", "thi thuc", "du hoc sinh",
    ),
    "guidelines-on-student-use-of-generative-artificial-intelligence": (
        # GENERATIVE AI specifically — NOT bare "artificial intelligence" (that also names the AI *minor*,
        # a different doc). Keeping it generative-specific stops a wrong pin on the "AI minor" questions.
        "generative ai", "generative artificial", "ai tao sinh", "tao sinh", "gen ai",
    ),
    "course-evaluation": (
        "course evaluation", "danh gia mon", "danh gia hoc phan", "danh gia cuoi khoa", "course eval",
    ),
    "guideline-for-program-change-request": (
        "program change", "change of program", "change program", "doi chuong trinh", "chuyen chuong trinh",
    ),
    "formal-escalation-management-procedure-for-students": (
        "escalation", "khieu nai", "grievance", "phan anh", "complaint procedure",
    ),
    "procedure-for-undergraduate-graduation-review-and-degree-conferral": (
        "graduation review", "degree conferral", "xet tot nghiep", "cap bang tot nghiep", "conferral",
    ),
    "minor-fields-information": (
        "minor field", "minor", "nganh phu", "hoc nganh phu",
    ),
    "outbound-student-exchange-procedure": (
        "outbound exchange", "student exchange", "exchange program", "exchange semester",
        "trao doi sinh vien", "chuong trinh trao doi", "di trao doi", "hoc ky trao doi",
    ),
    "guidelines-for-thesis-and-dissertation-submission": (
        "thesis", "dissertation", "luan van", "luan an",
    ),
    "procedure-for-requesting-a-leave-of-absence-withdrawal-and-return-from-a-leave-of-absence": (
        "leave of absence", "bao luu", "tam nghi hoc", "tro lai hoc", "nghi hoc tam thoi",
    ),
}


def canonical_url(slug: str) -> str:
    return f"{POLICY_BASE_URL}{slug}/"


_AUTO_INDEX: dict[str, frozenset[str]] | None = None


def _auto_index(settings: Settings | None = None) -> dict[str, frozenset[str]]:
    """Lazy-load the ingest-built policy topic index (Phase 1.24): {source_url: salient title terms}, written
    by scripts/build_policy_topic_index.py. Used only as a FALLBACK after the curated map. Fail-open: a
    missing/unreadable file → {} (curated-only behavior, byte-identical to pre-1.24)."""
    global _AUTO_INDEX
    if _AUTO_INDEX is not None:
        return _AUTO_INDEX
    settings = settings or get_settings()
    if not getattr(settings, "enable_policy_auto_index", False):
        return {}  # gated off (default) → curated-only, byte-identical to pre-1.24 (don't cache; cheap)
    path = Path(settings.processed_data_dir) / "policy_topic_index.json"
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        _AUTO_INDEX = {url: frozenset(terms) for url, terms in raw.items() if terms}
    except Exception:
        _AUTO_INDEX = {}
    return _AUTO_INDEX


def reset_policy_index_for_tests() -> None:
    global _AUTO_INDEX
    _AUTO_INDEX = None


def match(user_message: str) -> str | None:
    """Return the canonical page URL for a confidently-matched policy topic, else None (fail-open).

    Resolution order: (1) the hand-curated `POLICY_TOPICS` (single-winner: exactly one topic's keyword in the
    folded question) — unchanged, high-precision; the golden cases all hit here so curated precision is
    preserved EXACTLY. (2) If NO curated keyword matches, the ingest-built title index (Phase 1.24): pin the
    canonical page whose title best overlaps the query's salient terms (unique max overlap; ties → None).
    (2) only adds coverage for the ~138 non-curated pages + future uploads."""
    folded = _fold(user_message or "")
    if not folded:
        return None
    hits = [slug for slug, keywords in POLICY_TOPICS.items() if any(kw in folded for kw in keywords)]
    if len(hits) == 1:
        return canonical_url(hits[0])
    if hits:  # >1 curated topics matched → ambiguous → fail-open (unchanged behaviour)
        return None
    # No curated keyword matched → ingest-index fallback (title-overlap single-winner).
    auto = _auto_index()
    if not auto:
        return None
    q_terms = _salient_terms(user_message)
    if not q_terms:
        return None
    scored = [(url, len(q_terms & terms)) for url, terms in auto.items()]
    scored = [(url, overlap) for url, overlap in scored if overlap > 0]
    if not scored:
        return None
    best = max(overlap for _, overlap in scored)
    winners = [url for url, overlap in scored if overlap == best]
    return winners[0] if len(winners) == 1 else None
