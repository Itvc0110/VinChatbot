from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

from vinchatbot.app.rag.context import (
    apply_metadata_boosts,
    dedup_by_text,
    expand_to_parent_sections,
    reorder_for_long_context,
    select_dynamic_k,
)
from vinchatbot.app.rag.query_engineering import reciprocal_rank_fusion


@dataclass
class _Item:
    id: str
    text: str
    score: float | None = None


def _scored(id: str, score: float, **meta):
    base = dict(source_trust=None, category=None, subcategory=None, academic_year=None, term=None, policy_code=None)
    base.update(meta)
    return SimpleNamespace(id=id, text="", score=score, metadata=SimpleNamespace(**base))


def test_canonical_doc_match_fact_intents():
    # Phase 1.30/S15+S16 doc-pin matcher: confident fact-topic → canonical URL; else None (fail-open).
    from vinchatbot.app.rag.canonical_lookup import ADMISSION_URL, AID_URL, canonical_doc_match
    assert canonical_doc_match("What minimum GPA do I need to apply?") == ADMISSION_URL
    assert canonical_doc_match("điều kiện xét tuyển đại học là gì") == ADMISSION_URL
    assert canonical_doc_match("What % tuition subsidy do students get?") == AID_URL
    assert canonical_doc_match("trợ cấp học phí cho sinh viên") == AID_URL
    # AID is narrowed (1.30b) to the SUBSIDY intent — broad "scholarship"/"financial support" questions whose
    # answer lives elsewhere must NOT pin the undergrad aid page (they regress via a flipped citation).
    assert canonical_doc_match("Who is eligible for the Vingroup Science and Technology Scholarship?") is None
    assert canonical_doc_match("What financial support do PhD students receive?") is None
    assert canonical_doc_match("What are the financial aid request deadlines?") is None
    # program: needs program-name AND a fact-context word
    assert "MD_Program-Specifications" in (canonical_doc_match("How many credits is the Doctor of Medicine program?") or "")
    assert "BSCS" in (canonical_doc_match("Chương trình Khoa học Máy tính có bao nhiêu tín chỉ?") or "")
    assert "data-science" in (canonical_doc_match("data science curriculum total credits") or "")
    # program name WITHOUT fact-context → no pin (won't hijack "who teaches CS")
    assert canonical_doc_match("Who teaches computer science at VinUni?") is None
    # DURATION question (1.30b) → no pin: the spec PDFs carry a dual-degree "5/5.5 years" distractor that
    # regresses duration Qs, and the vector path answers them cleanly → duration is NOT a fact-context word.
    assert canonical_doc_match("How many years is VinUni's Bachelor of Business Administration program?") is None
    assert canonical_doc_match("chương trình kỹ thuật điện kéo dài bao nhiêu năm") is None
    # two programs named → ambiguous → None
    assert canonical_doc_match("compare computer science and data science credits") is None
    # plain fee / calendar → None
    assert canonical_doc_match("How much is the tuition?") is None
    assert canonical_doc_match("When is the add-drop deadline?") is None


def test_litm_reorder_puts_best_at_both_ends():
    # input is relevance-descending
    out = reorder_for_long_context(["a", "b", "c", "d", "e"])
    assert out[0] == "a"  # most relevant first
    assert out[-1] == "b"  # second-most relevant last
    assert out[len(out) // 2] == "e"  # least relevant buried in the middle
    assert sorted(out) == ["a", "b", "c", "d", "e"]  # no item lost


def test_litm_reorder_short_lists_unchanged():
    assert reorder_for_long_context([]) == []
    assert reorder_for_long_context(["a"]) == ["a"]
    assert reorder_for_long_context(["a", "b"]) == ["a", "b"]


def test_dedup_drops_near_duplicates_keeping_first():
    items = [
        _Item("html", "the course drop deadline is october 9 2026 for fall"),
        _Item("pdf", "the course drop deadline is october 9 2026 for fall"),  # dup of html
        _Item("other", "tuition for nursing is 349 million vnd per year"),
    ]
    out = dedup_by_text(items, lambda i: i.text)
    assert [i.id for i in out] == ["html", "other"]


def test_select_dynamic_k_threshold_and_bounds():
    items = [_Item("a", "", 1.0), _Item("b", "", 0.9), _Item("c", "", 0.3), _Item("d", "", 0.1)]
    kept = select_dynamic_k(items, lambda i: i.score, enabled=True, min_k=1, max_k=8, ratio=0.5)
    assert [i.id for i in kept] == ["a", "b"]  # only scores >= 0.5*top kept


def test_select_dynamic_k_respects_min_k():
    items = [_Item("a", "", 1.0), _Item("b", "", 0.2)]
    kept = select_dynamic_k(items, lambda i: i.score, enabled=True, min_k=2, max_k=8, ratio=0.5)
    assert [i.id for i in kept] == ["a", "b"]  # backfilled to min_k


def test_select_dynamic_k_disabled_returns_top_max_k():
    items = [_Item(str(i), "", 1.0 - i / 10) for i in range(10)]
    kept = select_dynamic_k(items, lambda i: i.score, enabled=False, min_k=1, max_k=5, ratio=0.5)
    assert len(kept) == 5


def test_metadata_boost_prefers_trusted_source_on_tie():
    items = [_scored("low", 0.8, source_trust="external_low"), _scored("hi", 0.8, source_trust="official_high")]
    out = apply_metadata_boosts(items, "vinuni policy question", enabled=True)
    assert out[0].id == "hi"  # official_high boosted above external_low


def test_metadata_boost_rewards_policy_code_mention():
    items = [_scored("a", 0.9), _scored("b", 0.7, policy_code="POL-CSD-001-V1.0")]
    out = apply_metadata_boosts(items, "what does POL-CSD-001-V1.0 say?", enabled=True)
    assert out[0].id == "b"  # exact policy_code mention overtakes the higher base score


def test_metadata_boost_disambiguates_academic_year_by_month():
    # Phase 1.13: "tháng 6 năm 2026" → June 2026 → AY 2025-2026 (Sep→Aug). The exact-AY chunk must
    # outrank the 2026-2027 chunk even though BOTH labels contain "2026" (the old substring bug).
    items = [
        _scored("ay2627", 0.8, academic_year="2026-2027"),
        _scored("ay2526", 0.8, academic_year="2025-2026"),
    ]
    out = apply_metadata_boosts(items, "sự kiện tháng 6 năm 2026", enabled=True)
    assert out[0].id == "ay2526"


def test_metadata_boost_handles_frozen_retrievedchunk():
    # RetrievedChunk is a frozen dataclass; boosting must not mutate it in place.
    from vinchatbot.app.rag.retriever import RetrievedChunk

    def meta(**kw):
        base = dict(source_trust=None, category=None, subcategory=None, academic_year=None, term=None, policy_code=None)
        base.update(kw)
        return SimpleNamespace(**base)

    items = [
        RetrievedChunk(text="low", metadata=meta(source_trust="external_low"), score=0.8),
        RetrievedChunk(text="hi", metadata=meta(source_trust="official_high"), score=0.8),
    ]
    out = apply_metadata_boosts(items, "vinuni question", enabled=True)
    assert out[0].text == "hi"
    assert out[0].score and out[0].score > 0.8


def test_metadata_boost_disabled_is_noop_order():
    items = [_scored("a", 0.9, source_trust="external_low"), _scored("b", 0.8, source_trust="official_high")]
    out = apply_metadata_boosts(items, "q", enabled=False)
    assert [i.id for i in out] == ["a", "b"]


def _pchunk(text: str, *, parent: str | None, section: str | None, score: float, page=None, subcategory=None):
    from vinchatbot.app.rag.retriever import RetrievedChunk

    md = SimpleNamespace(parent_doc_id=parent, section_id=section, page_number=page, subcategory=subcategory)
    return RetrievedChunk(text=text, metadata=md, score=score)


def test_parent_doc_expands_chunk_to_full_section():
    # The matched fine chunk is replaced by the whole section's stitched text.
    sections = {
        ("doc1", "secA"): [
            ("Eligibility: full-time students may apply.", 1, "h1"),
            ("Procedure: submit the form to your advisor.", 2, "h2"),
        ]
    }
    chunks = [_pchunk("Procedure: submit the form to your advisor.", parent="doc1", section="secA", score=0.9)]
    out = expand_to_parent_sections(
        chunks, lambda p, s: sections[(p, s)], max_chars=4000, max_siblings=6
    )
    assert len(out) == 1
    # anchor leads, sibling appended in page order
    assert out[0].text.startswith("Procedure: submit the form to your advisor.")
    assert "Eligibility: full-time students may apply." in out[0].text
    assert out[0].score == 0.9  # rank/score preserved from the matched chunk


def test_parent_doc_passes_through_chunks_without_section():
    chunks = [_pchunk("standalone paragraph", parent="doc1", section=None, score=0.8)]
    out = expand_to_parent_sections(chunks, lambda p, s: [], max_chars=4000, max_siblings=6)
    assert out == chunks  # unchanged when there is no section to expand


def test_parent_doc_collapses_two_top_chunks_from_same_section():
    sections = {("doc1", "secA"): [("part one", 1, "h1"), ("part two", 2, "h2")]}
    chunks = [
        _pchunk("part one", parent="doc1", section="secA", score=0.9),
        _pchunk("part two", parent="doc1", section="secA", score=0.7),
    ]
    out = expand_to_parent_sections(
        chunks, lambda p, s: sections[(p, s)], max_chars=4000, max_siblings=6
    )
    assert len(out) == 1  # the two same-section chunks merge into one, kept at top rank
    assert "part one" in out[0].text and "part two" in out[0].text


def test_parent_doc_respects_max_chars_budget():
    sections = {("doc1", "secA"): [("A" * 50, 1, "h1"), ("B" * 50, 2, "h2"), ("C" * 50, 3, "h3")]}
    chunks = [_pchunk("A" * 50, parent="doc1", section="secA", score=0.9)]
    out = expand_to_parent_sections(
        chunks, lambda p, s: sections[(p, s)], max_chars=120, max_siblings=6
    )
    assert "C" * 50 not in out[0].text  # third sibling dropped by the char budget


def test_parent_doc_skips_excluded_subcategory():
    # Calendar is point-lookup tabular data; expanding it makes the model over-share adjacent
    # dates, so a skip-list keeps those chunks un-stitched.
    sections = {("doc1", "secA"): [("1-Oct add deadline", 1, "h1"), ("9-Oct drop deadline", 1, "h2")]}
    chunks = [_pchunk("1-Oct add deadline", parent="doc1", section="secA", score=0.9, subcategory="calendar")]
    out = expand_to_parent_sections(
        chunks,
        lambda p, s: sections[(p, s)],
        max_chars=4000,
        max_siblings=6,
        skip_subcategories=frozenset({"calendar"}),
    )
    assert out[0].text == "1-Oct add deadline"  # not expanded; adjacent drop date not pulled in
    assert "9-Oct" not in out[0].text


def test_reciprocal_rank_fusion_rewards_cross_list_agreement():
    list_a = [_Item("x", ""), _Item("y", ""), _Item("z", "")]
    list_b = [_Item("y", ""), _Item("x", ""), _Item("w", "")]
    fused = reciprocal_rank_fusion([list_a, list_b], key=lambda i: i.id)
    # x and y appear high in both lists -> they rank above singletons z and w
    assert set(i.id for i in fused[:2]) == {"x", "y"}
    assert fused[0].id in {"x", "y"}
