import asyncio
from types import SimpleNamespace

import vinchatbot.app.agents.tools as tools_mod
from vinchatbot.app.ingest.chunker import chunk_document
from vinchatbot.app.ingest.parsers import extract_calendar_events
from vinchatbot.app.rag.query_engineering import (
    is_list_lookup,
    is_point_lookup,
    normalize_date_phrases,
)
from vinchatbot.app.rag.retriever import InMemoryRetriever, QdrantHybridRetriever, RetrievedChunk
from vinchatbot.app.schemas.document import RawDocument


def test_to_qdrant_filter_drops_unindexed_keys():
    # A model can invent a filter key (e.g. "semester"); without a Qdrant payload index that 400s the
    # whole turn. _to_qdrant_filter must drop unindexed keys and keep only the indexed ones.
    flt = QdrantHybridRetriever._to_qdrant_filter(
        {"semester": "Fall", "term": "Fall", "category": "academic"}
    )
    assert {c.key for c in flt.must} == {"metadata.term", "metadata.category"}
    # All-unindexed → no filter at all (fall back to unfiltered retrieval, never a 400).
    assert QdrantHybridRetriever._to_qdrant_filter({"semester": "Fall"}) is None


def test_in_memory_retriever_returns_filtered_calendar_citation():
    async def run_test():
        raw = RawDocument(
            source_url="https://policy.vinuni.edu.vn/calendar.pdf",
            canonical_url="https://policy.vinuni.edu.vn/calendar.pdf",
            title="Academic Calendar",
            document_type="pdf",
            content="# Academic Calendar\n\nFall 2025 Instruction Begins - 15 September",
        )
        chunks = chunk_document(raw)
        retriever = InMemoryRetriever(chunks)

        results = await retriever.search(
            "Fall instruction begins",
            filters={"category": "academic", "subcategory": "calendar"},
        )

        assert results
        assert results[0].metadata.source_url == raw.source_url
        assert "15 September" in results[0].text

    asyncio.run(run_test())


def test_calendar_parser_extracts_deadline_like_events():
    raw = RawDocument(
        source_url="https://policy.vinuni.edu.vn/calendar.pdf",
        canonical_url="https://policy.vinuni.edu.vn/calendar.pdf",
        title="Academic Calendar",
        document_type="pdf",
        content=(
            "# Trang 1\n\n"
            "Fall 2025 Instruction Begins - 15 September\n"
            "Course Drop Deadline 3/10\n"
            "Unrelated campus text"
        ),
        metadata={"academic_year": "2025-2026"},
    )

    events = extract_calendar_events(raw)

    assert len(events) >= 2
    assert any("Drop Deadline" in event.event_name for event in events)
    assert all(event.source_url == raw.source_url for event in events)


class _CountingRetriever:
    """Duck-typed retriever that counts which methods the tool calls, so we can assert how many
    rerank calls a multi-query turn makes (each `search`/`rerank_fused` ≈ one Cohere rerank)."""

    def __init__(self, chunks):
        self._chunks = chunks
        self.search_calls = 0
        self.candidate_calls = 0
        self.fused_calls = 0
        self.search_expand_sections = None
        self.fused_expand_sections = None

    async def search(self, query, filters=None, limit=8, reorder=True, boost_hints=None, expand_sections=False):
        self.search_calls += 1
        self.search_expand_sections = expand_sections
        return self._chunks[:limit]

    async def search_candidates(self, query, filters=None, limit=8):
        self.candidate_calls += 1
        return self._chunks[:limit]

    async def rerank_fused(self, query, chunks, limit=8, boost_hints=None, reorder=True, expand_sections=False):
        self.fused_calls += 1
        self.fused_expand_sections = expand_sections
        return list(chunks)[:limit]


def _fake_chunks():
    raw = RawDocument(
        source_url="https://vinuni.edu.vn/library",
        canonical_url="https://vinuni.edu.vn/library",
        title="Library",
        document_type="html",
        content="# Hours\n\nThe library opens at 8am.\n\n# Contact\n\nEmail the library desk.",
    )
    return [RetrievedChunk(text=c.text, metadata=c.metadata, score=1.0) for c in chunk_document(raw)]


def _settings(
    rerank_after_fusion: bool = False,
    adaptive: bool = False,
    crosslingual: bool = False,
    reactive: bool = False,
    reactive_min_score: float = 0.35,
):
    return SimpleNamespace(
        enable_query_expansion=True,
        enable_rerank_after_fusion=rerank_after_fusion,
        enable_adaptive_retrieval=adaptive,
        enable_crosslingual_expansion=crosslingual,
        enable_reactive_expansion=reactive,
        reactive_expansion_min_score=reactive_min_score,
        enable_date_normalization=True,
        retrieval_max_k=8,
        retrieval_candidate_k=40,
        enable_litm_reorder=True,
        enable_indirect_injection_scan=False,
        enable_soft_routing=True,
    )


def _run_tool(
    monkeypatch,
    *,
    rerank_after_fusion: bool = False,
    adaptive: bool = False,
    crosslingual: bool = False,
    reactive: bool = False,
    reactive_min_score: float = 0.35,
    tool_name: str = "search_vinuni",
    query: str = "library hours and services",
) -> "_CountingRetriever":
    retriever = _CountingRetriever(_fake_chunks())
    retriever.expand_calls = []  # list of (paraphrase, cross_lingual) tuples expand_query saw

    async def fake_expand(query, settings, *args, **kwargs):
        retriever.expand_calls.append((kwargs.get("paraphrase"), kwargs.get("cross_lingual")))
        return [query, f"{query} variant 2", f"{query} variant 3"]

    monkeypatch.setattr(tools_mod, "expand_query", fake_expand)
    monkeypatch.setattr(
        tools_mod,
        "get_settings",
        lambda: _settings(rerank_after_fusion, adaptive, crosslingual, reactive, reactive_min_score),
    )

    tools = tools_mod.build_retrieval_tools(retriever)
    tool = next(t for t in tools if t.name == tool_name)
    asyncio.run(tool.ainvoke({"query": query}))
    return retriever


def test_reactive_skips_expansion_when_first_result_is_strong(monkeypatch):
    # Strong first result (score 1.0 >= 0.35) → one deterministic single query, no expansion at all.
    retriever = _run_tool(monkeypatch, rerank_after_fusion=True, reactive=True)
    assert retriever.search_calls == 1
    assert retriever.candidate_calls == 0
    assert retriever.fused_calls == 0
    assert retriever.expand_calls == []  # expand_query never invoked → deterministic + cheap


def test_reactive_escalates_to_expansion_when_first_result_is_weak(monkeypatch):
    # Force "weak" by setting the threshold above the fake score (1.0 < 2.0) → escalate to expansion.
    retriever = _run_tool(
        monkeypatch, rerank_after_fusion=True, reactive=True, reactive_min_score=2.0
    )
    assert retriever.search_calls == 1  # the initial single query
    assert retriever.candidate_calls == 3  # then the expansion fan-out
    assert retriever.fused_calls == 1
    assert len(retriever.expand_calls) == 1


def test_normalize_date_phrases_converges_across_forms():
    # The 3 surface forms of the same month+year must all yield the SAME canonical set (query+variants),
    # so retrieval is phrasing-independent (Phase 1.12).
    for q in ("events for 6/2026", "sự kiện tháng 6 năm 2026", "events in June 2026"):
        blob = (q + " " + " ".join(normalize_date_phrases(q))).lower()  # query + its added variants
        assert "tháng 6 năm 2026" in blob
        assert "june 2026" in blob
        assert ("6/2026" in blob) or ("06/2026" in blob)


def test_normalize_date_phrases_no_false_positives():
    assert normalize_date_phrases("How do I register for courses?") == []
    assert normalize_date_phrases("tuition for Summer 2026") == []  # 'Summer' is not a month
    assert normalize_date_phrases("graduate in 2026") == []  # bare year, no month


def test_reactive_keeps_cross_lingual_translation_on_by_default(monkeypatch):
    # Cross-lingual VI<->EN translation stays ON in the default reactive path (recall lever); the
    # same-language paraphrase flood is gated off; a strong result → no escalation.
    retriever = _run_tool(monkeypatch, rerank_after_fusion=True, reactive=True, crosslingual=True)
    assert retriever.expand_calls == [(False, True)]  # translation only (paraphrase off), no escalation
    assert retriever.candidate_calls == 3
    assert retriever.fused_calls == 1
    assert retriever.search_calls == 0


def test_multi_query_default_reranks_once_per_variant(monkeypatch):
    retriever = _run_tool(monkeypatch, rerank_after_fusion=False)
    assert retriever.search_calls == 3  # current behavior: one rerank per query variant
    assert retriever.fused_calls == 0


def test_rerank_after_fusion_reranks_exactly_once(monkeypatch):
    retriever = _run_tool(monkeypatch, rerank_after_fusion=True)
    assert retriever.candidate_calls == 3  # candidates fetched per variant, no rerank
    assert retriever.fused_calls == 1  # single rerank on the fused pool
    assert retriever.search_calls == 0


def _meta(cid):
    return {
        "chunk_id": cid, "source_url": "u", "canonical_url": "u",
        "document_title": "T", "parent_doc_id": "p", "content_hash": "h",
    }


class _JitterStore:
    """Fake vector store reproducing the Phase 1.23d failure: a STABLE high-score core plus a 2-doc
    low-score tail whose ids swap every call (the approximate-search boundary jitter). Records the k it
    was asked to fetch."""

    def __init__(self, core: int):
        self.core = core
        self.last_k = None
        self.calls = 0

    async def asimilarity_search_with_score(self, query, k, filter=None):
        self.last_k = k
        self.calls += 1
        docs = [
            (SimpleNamespace(page_content=f"t{i}", metadata=_meta(f"c{i:03d}")), 1.0 - i * 0.01)
            for i in range(self.core)
        ]
        tail = ["Z1", "Z2"] if self.calls % 2 else ["Y1", "Y2"]  # jitter: tail ids alternate per call
        docs += [(SimpleNamespace(page_content="tail", metadata=_meta(t)), 0.001) for t in tail]
        return docs


def _fetch_retriever(margin: int, candidate_k: int = 10):
    r = QdrantHybridRetriever.__new__(QdrantHybridRetriever)  # bypass __init__ (no reranker/network)
    r.backend = "memory"
    r.settings = SimpleNamespace(
        enable_dynamic_k=True, retrieval_candidate_k=candidate_k, retrieval_overfetch_margin=margin
    )
    return r


def test_overfetch_truncate_absorbs_boundary_jitter():
    # margin>0: over-fetch candidate_k+margin, then truncate to candidate_k → the jittery low-score tail
    # lands in the discarded tail, so the returned candidate SET is identical across calls.
    r = _fetch_retriever(margin=4, candidate_k=10)
    store = _JitterStore(core=12)
    r.vector_store = store

    async def run():
        first = [c.metadata.chunk_id for c in await r._fetch_candidates("q", None, 8)]
        second = [c.metadata.chunk_id for c in await r._fetch_candidates("q", None, 8)]
        return first, second

    first, second = asyncio.run(run())
    assert store.last_k == 14  # candidate_k(10) + margin(4): over-fetch happened
    assert len(first) == 10  # truncated back to candidate_k
    assert first == second  # jitter absorbed → deterministic set AND order
    assert not ({"Z1", "Z2", "Y1", "Y2"} & set(first))  # the jittery tail is discarded


def test_overfetch_margin_zero_is_byte_identical_and_jitters():
    # margin=0 (default/OFF): fetch exactly candidate_k, no truncation → behaviour is unchanged from
    # pre-1.23d, and the boundary jitter is NOT absorbed (the tail is within the returned set).
    r = _fetch_retriever(margin=0, candidate_k=10)
    store = _JitterStore(core=8)  # 8 core + 2 tail = exactly candidate_k
    r.vector_store = store

    async def run():
        first = {c.metadata.chunk_id for c in await r._fetch_candidates("q", None, 8)}
        second = {c.metadata.chunk_id for c in await r._fetch_candidates("q", None, 8)}
        return first, second

    first, second = asyncio.run(run())
    assert store.last_k == 10  # no over-fetch: asked for exactly candidate_k
    assert first != second  # jitter NOT absorbed (margin off) — documents the failure mode


def test_is_point_lookup_truth_table():
    assert is_point_lookup("anything at all", category="calendar")
    assert is_point_lookup("anything at all", category="financial")
    assert is_point_lookup("When is the Fall 2026 final exam?")  # year + term + exam
    assert is_point_lookup("Học phí ngành Điều dưỡng là bao nhiêu?")  # "học phí"
    assert is_point_lookup("What is the tuition per credit?")  # "tuition"
    assert not is_point_lookup("What services does the library offer?", category="services")
    assert not is_point_lookup("How do I appeal an academic decision?")


def test_is_list_lookup_truth_table():
    # Fires on genuine multi-row "list" intent (EN + unambiguous VI).
    assert is_list_lookup("What is the per-credit tuition for all programs?")
    assert is_list_lookup("Compare the annual tuition across programs")
    assert is_list_lookup("Học phí mỗi tín chỉ của tất cả các chương trình là bao nhiêu?")  # "tất cả"
    assert is_list_lookup("Liệt kê học phí của từng chương trình.")  # "liệt kê"
    # Must NOT fire on single-target point-lookups or VI RATE words (Phase 1.27a over-fire guard):
    assert not is_list_lookup("What is the per-credit tuition for nursing?")
    assert not is_list_lookup("Phí phạt trả trễ mỗi ngày là bao nhiêu?")  # "mỗi ngày" = per day, NOT a list
    assert not is_list_lookup("Học phí mỗi tín chỉ ngành Điều dưỡng?")  # "mỗi tín chỉ" = per credit (rate)
    assert not is_list_lookup("Các quy định về liêm chính học thuật là gì?")  # "các" (the/plural)


def test_calendar_point_lookup_no_expansion_when_crosslingual_off(monkeypatch):
    # Calendar point-lookup, cross-lingual OFF: NO expansion at all (paraphrase off + xling off) +
    # single-query full-section read (the Phase 1.7 precision path).
    retriever = _run_tool(
        monkeypatch,
        adaptive=True,
        rerank_after_fusion=True,
        crosslingual=False,
        tool_name="search_academic_calendar",
        query="Summer 2027 final exam dates",
    )
    assert retriever.expand_calls == []  # expand_query not called
    assert retriever.search_calls == 1
    assert retriever.search_expand_sections is True
    assert retriever.candidate_calls == 0 and retriever.fused_calls == 0


def test_calendar_point_lookup_crosslingual_only_no_paraphrase(monkeypatch):
    # Calendar point-lookup, cross-lingual ON (Phase 1.8): translation variant but NO paraphrase
    # flood → fuse + rerank once + full section.
    retriever = _run_tool(
        monkeypatch,
        adaptive=True,
        rerank_after_fusion=True,
        crosslingual=True,
        tool_name="search_academic_calendar",
        query="Lịch thi cuối kỳ Summer 2027",
    )
    assert retriever.expand_calls == [(False, True)]  # paraphrase OFF, cross-lingual ON
    assert retriever.candidate_calls == 3  # variants fused (no rerank per variant)
    assert retriever.fused_calls == 1
    assert retriever.fused_expand_sections is True
    assert retriever.search_calls == 0


def test_financial_point_lookup_paraphrase_and_crosslingual(monkeypatch):
    # Financial point-lookup, cross-lingual ON: paraphrase AND cross-lingual + full section.
    retriever = _run_tool(
        monkeypatch,
        adaptive=True,
        rerank_after_fusion=True,
        crosslingual=True,
        tool_name="search_financial_regulations",
        query="Học phí ngành Điều dưỡng là bao nhiêu?",
    )
    assert retriever.expand_calls == [(True, True)]  # both kinds requested
    assert retriever.candidate_calls == 3
    assert retriever.fused_calls == 1
    assert retriever.fused_expand_sections is True
    assert retriever.search_calls == 0

