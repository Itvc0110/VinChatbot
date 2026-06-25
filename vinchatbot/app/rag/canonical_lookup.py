"""Deterministic canonical-doc selection for fact-intents (Phase 1.30/S15+S16).

Generalizes the policy doc-pin (Phase 1.21, `policy_lookup`) to the new-content fact-intents. The boost
approach (1.30a) was A/B-rejected: the authoritative doc (admissions general-admissions FAQ = GPA 8.0; the
scholarship page = 35% subsidy; the program curriculum/spec PDF = 228/120/126 credits) is OUT-RANKED by magnet
prose (tariff/regs/FAQ/exchange/bio) and often not retrieved at all, so a score nudge can't lift it. Instead we
SELECT the doc deterministically: when a question confidently names an admission / financial-aid / program-
credits topic, the caller (`tools._search`) fetches that canonical page by `source_url` and pins it to the
front of context (the caller re-ranks WITHIN the pinned doc with the real query, so the fact-bearing chunk
surfaces — verified 2026-06-25 against vinuni_full_e5_v2).

Single-winner + fail-open (mirrors `policy_lookup` / `structured_lookup`): 0 or >1 matches ⇒ None ⇒ the vector
path is byte-identical. Keywords are written ACCENT-FREE (the query is `_fold`-ed before matching). Pure
dict/regex, no LLM/network. URLs are curated (maintained like POLICY_TOPICS); a stale/404 URL → empty pin
fetch → fail-open.
"""

from __future__ import annotations

from vinchatbot.app.rag.context import _fold

# Admission and financial-aid each map to ONE stable canonical page (verified to carry the facts in v2).
ADMISSION_URL = "https://admissions.vinuni.edu.vn/undergraduate/faqs/general-admissions/"
AID_URL = "https://admissions.vinuni.edu.vn/scholarship-and-financial-aid/undergraduate-programs/scholarships/"

# Distinctive ACCENT-FREE keyword phrases per category. Admission/aid keywords are fact-specific; program
# matching additionally requires a fact-context word (below) so "who teaches CS" does not pin a curriculum.
# AID is deliberately narrowed (1.30b) to the TUITION-SUBSIDY intent only — the AID page is curated for the
# "all undergrads receive a 35% tuition subsidy" fact. The broad "scholarship" / "financial aid/support"
# terms were REMOVED because they over-fire onto questions whose answer lives elsewhere (named scholarships
# like Vingroup S&T on scholarships.vinuni, PhD funding, financial-aid request DEADLINES on a policy page) —
# pinning the undergrad aid page there flips the citation. Those revert to the vector path (baseline-clean).
_AID_KW = (
    "subsid", "tuition subsidy", "tuition support", "tro cap", "ho tro hoc phi", "mien giam hoc phi",
)
_ADMISSION_KW = (
    "admission requirement", "minimum gpa", "required gpa", "gpa requirement", "to apply", "how to apply",
    "entry requirement", "admission criteria", "xet tuyen", "tuyen sinh", "dieu kien dau vao",
    "dieu kien xet tuyen", "dieu kien tuyen sinh", "diem trung binh", "diem chuan", "nop ho so", "nop don",
)
# Program name -> curated canonical curriculum/spec URL (current-cohort doc that states the credits/duration).
PROGRAM_TOPICS: dict[str, tuple[str, ...]] = {
    "https://policy.vinuni.edu.vn/wp-content/uploads/2025/08/vF_250816_BSCS_25-29_Curriculum-Framework.pdf": (
        "computer science", "khoa hoc may tinh", "bscs",
    ),
    "https://cecs.vinuni.edu.vn/undergraduate/data-science/": (
        "data science", "khoa hoc du lieu", "bsds",
    ),
    "https://policy.vinuni.edu.vn/wp-content/uploads/2026/01/MD_Program-Specifications.pdf": (
        "doctor of medicine", "medical doctor", "bac si y khoa", "nganh y khoa", "chuong trinh y khoa",
    ),
    "https://policy.vinuni.edu.vn/wp-content/uploads/2025/09/vF_250916_BN-program_AY2526-CF.pdf": (
        "nursing", "dieu duong",
    ),
    "https://policy.vinuni.edu.vn/wp-content/uploads/2026/01/BBA_Program-Specifications.pdf": (
        "business administration", "quan tri kinh doanh", "bba",
    ),
}
# Program-fact context: only pin a program curriculum when the question is about its CREDITS / curriculum
# STRUCTURE (not a club, a dean, or DURATION). Duration ("how many years") is deliberately EXCLUDED (1.30b):
# the spec PDFs carry a dual-degree "after 5 or 5.5 years, students receive [a partner-university degree]"
# timeline that competes with the "Length of program: 4 years" line, so pinning the spec regresses duration
# questions — the vector path already answers them cleanly from the cohort docs. ACCENT-FREE.
_PROGRAM_FACT_KW = (
    "credit", "tin chi", "curriculum", "chuong trinh dao tao", "chuong trinh hoc", "total credit",
    "bao nhieu tin chi",
)


def canonical_doc_match(user_message: str) -> str | None:
    """Canonical page URL for a confidently-matched fact-topic, else None (fail-open). Checked
    aid → admission → program (most→least specific). Program needs a program-name AND a fact-context word,
    single-winner across programs."""
    folded = _fold(user_message or "")
    if not folded:
        return None
    if any(kw in folded for kw in _AID_KW):
        return AID_URL
    if any(kw in folded for kw in _ADMISSION_KW):
        return ADMISSION_URL
    if any(kw in folded for kw in _PROGRAM_FACT_KW):
        hits = [url for url, names in PROGRAM_TOPICS.items() if any(n in folded for n in names)]
        if len(hits) == 1:
            return hits[0]
    return None
