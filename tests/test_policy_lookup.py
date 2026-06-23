from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import pytest

import vinchatbot.app.agents.tools as tools_mod
from vinchatbot.app.ingest.chunker import chunk_document
from vinchatbot.app.rag import policy_lookup as PL
from vinchatbot.app.rag.retriever import RetrievedChunk
from vinchatbot.app.schemas.document import RawDocument

PIN_URL = PL.canonical_url("library-policies-for-users")


@pytest.fixture(autouse=True)
def _isolate_auto_index(monkeypatch):
    # Default every test to NO ingest index (curated-only) so they don't read the real
    # data/processed/policy_topic_index.json; the 1.24 tests opt in by overriding _AUTO_INDEX.
    monkeypatch.setattr(PL, "_AUTO_INDEX", {})


# ---- match(): curated single-winner topic selection ------------------------------------------

def test_match_distinctive_vi_topic():
    assert PL.match("Tôi được mượn bao nhiêu tài liệu từ thư viện?") == PIN_URL


def test_match_distinctive_en_topic():
    assert PL.match("How many feedback sessions must the internship supervisor hold?") == \
        PL.canonical_url("internship-management-policy")


def test_match_generative_ai_not_ai_minor():
    # "generative AI" -> the GenAI guideline; "AI minor" -> the minor-fields doc (not GenAI). The curated
    # keywords keep these apart so neither pins the other (the precision risk that sank the title-boost).
    assert PL.match("Which students do the generative AI guidelines apply to?") == \
        PL.canonical_url("guidelines-on-student-use-of-generative-artificial-intelligence")
    assert PL.match("How many credits is the Artificial Intelligence minor for BBA students?") == \
        PL.canonical_url("minor-fields-information")


def test_match_miss_when_no_topic():
    assert PL.match("Bãi đỗ xe cho sinh viên ở đâu?") is None  # parking — no curated topic


def test_match_miss_when_ambiguous():
    # names TWO topics → >1 winner → fail-open (None), never a wrong pin
    assert PL.match("leave of absence and academic integrity") is None


def test_match_empty():
    assert PL.match("") is None
    assert PL.match("   ") is None


# ---- Phase 1.24: ingest-index fallback (curated-first) --------------------------------------

def test_auto_index_fallback_pins_noncurated(monkeypatch):
    # A policy NOT in the curated 17, with a distinctive title → pinned via the ingest index.
    monkeypatch.setattr(PL, "_AUTO_INDEX", {
        "https://policy.vinuni.edu.vn/all-policies/visiting-scholar-policy/": frozenset({"visiting", "scholar"}),
        "https://policy.vinuni.edu.vn/all-policies/parking-regulations/": frozenset({"parking", "vehicle"}),
    })
    assert PL.match("What does the visiting scholar policy say?") == \
        "https://policy.vinuni.edu.vn/all-policies/visiting-scholar-policy/"


def test_curated_takes_precedence_over_auto(monkeypatch):
    # A curated keyword must win even if the auto index has a decoy entry (curated checked first).
    monkeypatch.setattr(PL, "_AUTO_INDEX", {"https://x/decoy/": frozenset({"library"})})
    assert PL.match("Tôi được mượn bao nhiêu tài liệu từ thư viện?") == \
        PL.canonical_url("library-policies-for-users")


def test_auto_index_tie_fails_open(monkeypatch):
    monkeypatch.setattr(PL, "_AUTO_INDEX", {
        "https://x/a/": frozenset({"scholarship"}),
        "https://x/b/": frozenset({"scholarship"}),
    })
    assert PL.match("scholarship question") is None  # tie on overlap → fail-open


def test_auto_index_absent_is_curated_only(monkeypatch):
    monkeypatch.setattr(PL, "_AUTO_INDEX", {})  # no ingest index → curated-only, byte-identical to pre-1.24
    assert PL.match("some entirely uncurated topic about xyz parking") is None


# ---- pin seam in tools._search ---------------------------------------------------------------

def _settings(pin: bool = False) -> SimpleNamespace:
    return SimpleNamespace(
        enable_query_expansion=False, enable_rerank_after_fusion=True, enable_adaptive_retrieval=False,
        enable_crosslingual_expansion=False, enable_reactive_expansion=True,
        reactive_expansion_min_score=0.35, enable_date_normalization=False, retrieval_max_k=8,
        retrieval_candidate_k=40, enable_litm_reorder=True, enable_indirect_injection_scan=False,
        enable_soft_routing=True, enable_structured_lookup=False, enable_crosslingual_policy=False,
        enable_canonical_policy_boost=False, enable_policy_doc_pin=pin,
    )


def _chunks(url: str, title: str, body: str, score: float) -> list[RetrievedChunk]:
    raw = RawDocument(source_url=url, canonical_url=url, title=title, document_type="html",
                      content=f"# {title}\n\n{body}")
    return [RetrievedChunk(text=c.text, metadata=c.metadata, score=score) for c in chunk_document(raw)]


class _PinRetr:
    """Returns the canonical doc only on a source_url-filtered fetch; generic chunks otherwise."""

    def __init__(self):
        self.source_url_filters: list[str] = []
        self._norm = _chunks("https://x.vinuni.edu.vn/magnet/", "Magnet Doc",
                             "Unrelated governance text that normally out-ranks the policy page.", 0.9)
        self._pinned = _chunks(PIN_URL, "Library Access & Services Policy",
                              "The canonical library policy: borrowing limits and loan periods.", 0.4)

    async def search(self, query, filters=None, limit=8, reorder=True, boost_hints=None, expand_sections=False):
        if filters and filters.get("source_url"):
            self.source_url_filters.append(filters["source_url"])
            return self._pinned[:limit]
        return self._norm[:limit]

    async def search_candidates(self, query, filters=None, limit=8):
        return self._norm[:limit]

    async def rerank_fused(self, query, chunks, limit=8, boost_hints=None, reorder=True, expand_sections=False):
        return list(chunks)[:limit]


def _run(monkeypatch, query: str, settings: SimpleNamespace, tool_name: str = "search_policy_documents"):
    retr = _PinRetr()
    monkeypatch.setattr(tools_mod, "get_settings", lambda: settings)
    monkeypatch.setattr(tools_mod, "get_user_message", lambda: query)
    tool = next(t for t in tools_mod.build_retrieval_tools(retr) if t.name == tool_name)
    out = json.loads(asyncio.run(tool.ainvoke({"query": query})))
    return out, retr


_LIB_Q = "Tôi được mượn bao nhiêu tài liệu từ thư viện?"


def test_pin_prepends_canonical_when_enabled(monkeypatch):
    out, retr = _run(monkeypatch, _LIB_Q, _settings(pin=True))
    assert PIN_URL in retr.source_url_filters  # targeted source_url fetch fired
    assert out["results"][0]["metadata"]["source_url"] == PIN_URL  # canonical doc leads the context


def test_pin_fires_for_financial_specialist(monkeypatch):
    # 1.21b: the pin must fire even when a policy question routes to the financial specialist
    # (subcat="financial") — that's exactly where finaid-vi landed and the old student_affairs gate missed it.
    out, retr = _run(monkeypatch, _LIB_Q, _settings(pin=True), tool_name="search_financial_regulations")
    assert PIN_URL in retr.source_url_filters
    assert out["results"][0]["metadata"]["source_url"] == PIN_URL


def test_pin_fires_for_general_specialist(monkeypatch):
    # 1.21b: also fires via the general search_vinuni tool (subcat=None) — where intern-vi/lib-vi routed.
    out, retr = _run(monkeypatch, _LIB_Q, _settings(pin=True), tool_name="search_vinuni")
    assert PIN_URL in retr.source_url_filters
    assert out["results"][0]["metadata"]["source_url"] == PIN_URL


def test_pin_skipped_for_calendar_specialist(monkeypatch):
    # 1.21b: calendar is the ONE excluded routing — protects date point-lookups that share a policy keyword.
    _, retr = _run(monkeypatch, _LIB_Q, _settings(pin=True), tool_name="search_academic_calendar")
    assert retr.source_url_filters == []  # calendar subcat → pin never fires


def test_pin_off_by_default(monkeypatch):
    out, retr = _run(monkeypatch, _LIB_Q, _settings(pin=False))
    assert retr.source_url_filters == []  # flag off → no targeted fetch (byte-identical path)
    assert out["results"][0]["metadata"]["source_url"] != PIN_URL


def test_pin_skipped_when_no_topic_match(monkeypatch):
    _, retr = _run(monkeypatch, "Sinh viên đỗ xe máy ở khu vực nào trong trường?", _settings(pin=True))
    assert retr.source_url_filters == []  # match() miss → fail-open, no pin
