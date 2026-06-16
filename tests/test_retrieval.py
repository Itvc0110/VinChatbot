import asyncio
from types import SimpleNamespace

import vinchatbot.app.agents.tools as tools_mod
from vinchatbot.app.ingest.chunker import chunk_document
from vinchatbot.app.ingest.parsers import extract_calendar_events
from vinchatbot.app.rag.query_engineering import is_point_lookup
from vinchatbot.app.rag.retriever import InMemoryRetriever, RetrievedChunk
from vinchatbot.app.schemas.document import RawDocument


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


def _settings(rerank_after_fusion: bool = False, adaptive: bool = False, crosslingual: bool = False):
    return SimpleNamespace(
        enable_query_expansion=True,
        enable_rerank_after_fusion=rerank_after_fusion,
        enable_adaptive_retrieval=adaptive,
        enable_crosslingual_expansion=crosslingual,
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
    tool_name: str = "search_vinuni",
    query: str = "library hours and services",
) -> "_CountingRetriever":
    retriever = _CountingRetriever(_fake_chunks())
    retriever.expand_calls = []  # list of (paraphrase, cross_lingual) tuples expand_query saw

    async def fake_expand(query, settings, *args, **kwargs):
        retriever.expand_calls.append((kwargs.get("paraphrase"), kwargs.get("cross_lingual")))
        return [query, f"{query} variant 2", f"{query} variant 3"]

    monkeypatch.setattr(tools_mod, "expand_query", fake_expand)
    monkeypatch.setattr(tools_mod, "get_settings", lambda: _settings(rerank_after_fusion, adaptive, crosslingual))

    tools = tools_mod.build_retrieval_tools(retriever)
    tool = next(t for t in tools if t.name == tool_name)
    asyncio.run(tool.ainvoke({"query": query}))
    return retriever


def test_multi_query_default_reranks_once_per_variant(monkeypatch):
    retriever = _run_tool(monkeypatch, rerank_after_fusion=False)
    assert retriever.search_calls == 3  # current behavior: one rerank per query variant
    assert retriever.fused_calls == 0


def test_rerank_after_fusion_reranks_exactly_once(monkeypatch):
    retriever = _run_tool(monkeypatch, rerank_after_fusion=True)
    assert retriever.candidate_calls == 3  # candidates fetched per variant, no rerank
    assert retriever.fused_calls == 1  # single rerank on the fused pool
    assert retriever.search_calls == 0


def test_is_point_lookup_truth_table():
    assert is_point_lookup("anything at all", category="calendar")
    assert is_point_lookup("anything at all", category="financial")
    assert is_point_lookup("When is the Fall 2026 final exam?")  # year + term + exam
    assert is_point_lookup("Học phí ngành Điều dưỡng là bao nhiêu?")  # "học phí"
    assert is_point_lookup("What is the tuition per credit?")  # "tuition"
    assert not is_point_lookup("What services does the library offer?", category="services")
    assert not is_point_lookup("How do I appeal an academic decision?")


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

