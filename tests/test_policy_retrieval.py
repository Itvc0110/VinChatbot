from __future__ import annotations

import asyncio
from types import SimpleNamespace

import vinchatbot.app.agents.tools as tools_mod
from vinchatbot.app.ingest.chunker import chunk_document
from vinchatbot.app.rag.context import apply_metadata_boosts
from vinchatbot.app.rag.retriever import RetrievedChunk
from vinchatbot.app.schemas.document import RawDocument


def _settings(crosslingual_policy: bool = False, canonical_boost: bool = False) -> SimpleNamespace:
    return SimpleNamespace(
        enable_query_expansion=True,
        enable_rerank_after_fusion=True,
        enable_adaptive_retrieval=False,
        enable_crosslingual_expansion=False,
        enable_reactive_expansion=True,
        reactive_expansion_min_score=0.35,
        enable_date_normalization=False,
        retrieval_max_k=8,
        retrieval_candidate_k=40,
        enable_litm_reorder=True,
        enable_indirect_injection_scan=False,
        enable_soft_routing=True,
        enable_structured_lookup=False,
        enable_crosslingual_policy=crosslingual_policy,
        enable_canonical_policy_boost=canonical_boost,
    )


class _Retr:
    def __init__(self):
        raw = RawDocument(
            source_url="https://policy.vinuni.edu.vn/all-policies/x/",
            canonical_url="https://policy.vinuni.edu.vn/all-policies/x/",
            title="X",
            document_type="html",
            content="# Policy X\n\nSome policy prose for the vector path.",
        )
        self._c = [RetrievedChunk(text=c.text, metadata=c.metadata, score=1.0) for c in chunk_document(raw)]
        self.boost_hints_seen = None

    async def search(self, query, filters=None, limit=8, reorder=True, boost_hints=None, expand_sections=False):
        self.boost_hints_seen = boost_hints
        return self._c[:limit]

    async def search_candidates(self, query, filters=None, limit=8):
        return self._c[:limit]

    async def rerank_fused(self, query, chunks, limit=8, boost_hints=None, reorder=True, expand_sections=False):
        self.boost_hints_seen = boost_hints
        return list(chunks)[:limit]


def _run_policy_tool(monkeypatch, query, settings):
    """Invoke search_policy_documents; capture the cross_lingual flag expand_query saw + boost_hints."""
    retr = _Retr()
    captured_cross = []

    async def fake_expand(q, s, *a, **k):
        captured_cross.append(k.get("cross_lingual"))
        return [q, f"{q} (translated)"]

    monkeypatch.setattr(tools_mod, "expand_query", fake_expand)
    monkeypatch.setattr(tools_mod, "get_settings", lambda: settings)
    tools = tools_mod.build_retrieval_tools(retr)
    tool = next(t for t in tools if t.name == "search_policy_documents")
    asyncio.run(tool.ainvoke({"query": query}))
    return captured_cross, retr


# ---- Lever 1: language-aware cross-lingual escalation for VI policy queries -------------------

def test_crosslingual_policy_fires_for_vi(monkeypatch):
    cross, _ = _run_policy_tool(
        monkeypatch, "Chính sách liêm chính học thuật áp dụng cho đối tượng nào?",
        _settings(crosslingual_policy=True),
    )
    assert True in cross  # EN translation variant forced for the VI policy query


def test_crosslingual_policy_not_for_en(monkeypatch):
    cross, _ = _run_policy_tool(
        monkeypatch, "Who does the academic integrity policy apply to?",
        _settings(crosslingual_policy=True),
    )
    assert True not in cross  # EN query → no forced cross-lingual (clean native pass)


def test_crosslingual_policy_off_by_default(monkeypatch):
    cross, _ = _run_policy_tool(
        monkeypatch, "Chính sách liêm chính học thuật áp dụng cho đối tượng nào?",
        _settings(crosslingual_policy=False),
    )
    assert True not in cross  # flag off → byte-identical to today


def test_canonical_boost_hint_passed_when_enabled(monkeypatch):
    _, retr = _run_policy_tool(
        monkeypatch, "Who does the academic integrity policy apply to?",
        _settings(canonical_boost=True),
    )
    assert (retr.boost_hints_seen or {}).get("prefer_canonical") is True


def test_canonical_topic_terms_threaded_for_vi(monkeypatch):
    # VI policy query + both flags on → Lever 1 forces the EN translation variant, and Lever 2 threads
    # those variants as `topic_terms` so the boost can match the EN canonical title cross-lingually.
    _, retr = _run_policy_tool(
        monkeypatch, "Chính sách thư viện cho mượn sách trong bao lâu?",
        _settings(crosslingual_policy=True, canonical_boost=True),
    )
    hints = retr.boost_hints_seen or {}
    assert hints.get("prefer_canonical") is True
    assert "translated" in (hints.get("topic_terms") or "")  # EN variant threaded for title matching


# ---- Lever 2: topic-targeted canonical policy-page boost -------------------------------------

def _scored(cid: str, score: float, **meta):
    base = dict(source_trust=None, category=None, subcategory=None, academic_year=None, term=None,
                policy_code=None, document_type=None, document_title=None)
    base.update(meta)
    return SimpleNamespace(id=cid, text="", score=score, metadata=SimpleNamespace(**base))


def _canon_vs_reg(query, hints, canon_title="Academic Integrity Policy"):
    # A governance PDF with a HIGHER raw score vs the canonical detail page with a lower raw score.
    items = [
        _scored("reg", 1.00, document_type="policy_pdf", source_trust="official_high",
                document_title="Undergraduate Training Regulations"),
        _scored("canon", 0.95, document_type="policy_html", source_trust="official_high",
                document_title=canon_title),
    ]
    return apply_metadata_boosts(items, query, hints=hints, enabled=True)


def test_canonical_boost_lifts_on_topic_policy_html():
    # Title topic ("integrity") overlaps the query → canonical detail page lifted above the higher-raw pdf.
    out = _canon_vs_reg("academic integrity policy scope", {"prefer_canonical": True})
    assert out[0].id == "canon"


def test_canonical_boost_skipped_when_offtopic():
    # Title topic ("library") does NOT overlap an academic-integrity query → NO boost (raw order kept).
    # This is the anti-regression gate: the blanket version wrongly lifted every policy_html here.
    out = _canon_vs_reg("academic integrity policy scope", {"prefer_canonical": True},
                        canon_title="Library Access & Services Policy")
    assert out[0].id == "reg"


def test_canonical_boost_uses_crosslingual_topic_terms():
    vi_q = "Thư viện cho mượn sách trong bao lâu?"  # VI alone: "thu vien" never matches the EN title
    # Without topic_terms: VI query tokens don't overlap the EN canonical title → no boost.
    out_no = _canon_vs_reg(vi_q, {"prefer_canonical": True}, canon_title="Library Access & Services Policy")
    assert out_no[0].id == "reg"
    # With cross-lingual topic_terms (Lever 1's EN translation): "library" overlaps → canonical lifted.
    out_yes = _canon_vs_reg(
        vi_q,
        {"prefer_canonical": True, "topic_terms": vi_q + " how long is the library borrowing period"},
        canon_title="Library Access & Services Policy",
    )
    assert out_yes[0].id == "canon"


def test_no_canonical_boost_without_hint():
    out = _canon_vs_reg("academic integrity policy scope", {})
    assert out[0].id == "reg"  # no hint → raw order preserved (no false boost)
