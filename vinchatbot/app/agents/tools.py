from __future__ import annotations

import asyncio
import json
from typing import Any

from vinchatbot.app.agents.guardrails import scan_for_injection
from vinchatbot.app.core.config import get_settings
from vinchatbot.app.core.observability import mark_point_lookup
from vinchatbot.app.rag.citations import excerpt
from vinchatbot.app.rag.context import dedup_by_text, reorder_for_long_context
from vinchatbot.app.rag.query_engineering import (
    expand_query,
    is_point_lookup,
    reciprocal_rank_fusion,
)
from vinchatbot.app.rag.retriever import Retriever


def build_retrieval_tools(retriever: Retriever):
    try:
        from langchain.tools import tool
    except ImportError as exc:
        raise RuntimeError("Install langchain to build agent tools.") from exc

    async def _search(
        query: str,
        filters: dict[str, Any] | None = None,
        enforced_filters: dict[str, Any] | None = None,
    ) -> str:
        settings = get_settings()
        caller_filters = {key: value for key, value in (filters or {}).items() if value}

        # Soft routing: the specialist's category goes in as a *boost hint* (not a hard
        # filter), so a mis-route never blanks out results. Otherwise enforce it.
        if settings.enable_soft_routing:
            merged_filters = caller_filters
            boost_hints = enforced_filters or None
        else:
            merged_filters = {**caller_filters, **(enforced_filters or {})}
            boost_hints = None

        max_k = settings.retrieval_max_k
        routed = enforced_filters or {}
        subcat = routed.get("subcategory") or routed.get("category")
        point_lookup = settings.enable_adaptive_retrieval and is_point_lookup(query, subcat)
        if point_lookup:
            mark_point_lookup()
        expand_sections = point_lookup
        fuse_then_rerank = settings.enable_rerank_after_fusion or point_lookup

        # Adaptive (Phase 1.7) domain split: a calendar date-grid's neighbours are pure distractors,
        # so calendar point-lookups DROP expansion (precision); financial/other point-lookups KEEP
        # expansion and add an English variant (cross-lingual recall for the EN tariff). Both read the
        # full section + a strict prompt so the model picks the exact row.
        if point_lookup and subcat == "calendar":
            queries = [query]
        elif settings.enable_query_expansion:
            queries = await expand_query(query, settings, cross_lingual=point_lookup)
        else:
            queries = [query]

        if len(queries) > 1 and fuse_then_rerank:
            # Retrieve candidates per variant WITHOUT reranking, RRF-fuse, then rerank ONCE.
            candidate_lists = await asyncio.gather(
                *(
                    retriever.search_candidates(query=q, filters=merged_filters, limit=max_k)
                    for q in queries
                )
            )
            fused = reciprocal_rank_fusion(candidate_lists, key=lambda chunk: chunk.metadata.chunk_id)
            fused = dedup_by_text(fused, lambda chunk: chunk.text)[: settings.retrieval_candidate_k]
            chunks = await retriever.rerank_fused(
                query,
                fused,
                limit=max_k,
                boost_hints=boost_hints,
                reorder=settings.enable_litm_reorder,
                expand_sections=expand_sections,
            )
        elif len(queries) > 1:
            # Legacy per-variant rerank (only when rerank-after-fusion is off and not a point-lookup).
            ranked_lists = await asyncio.gather(
                *(
                    retriever.search(
                        query=q, filters=merged_filters, limit=max_k, reorder=False, boost_hints=boost_hints
                    )
                    for q in queries
                )
            )
            fused = reciprocal_rank_fusion(ranked_lists, key=lambda chunk: chunk.metadata.chunk_id)
            fused = dedup_by_text(fused, lambda chunk: chunk.text)[:max_k]
            chunks = reorder_for_long_context(fused) if settings.enable_litm_reorder else fused
        else:
            chunks = await retriever.search(
                query=query,
                filters=merged_filters,
                limit=max_k,
                boost_hints=boost_hints,
                expand_sections=expand_sections,
            )

        # Indirect-injection defense: drop retrieved chunks whose text carries injection
        # patterns so poisoned source content cannot steer the model.
        if settings.enable_indirect_injection_scan:
            chunks = [chunk for chunk in chunks if not scan_for_injection(chunk.text)]

        payload = {
            "results": [
                {
                    "text": excerpt(chunk.text, max_chars=900),
                    "score": chunk.score,
                    "metadata": chunk.metadata.model_dump(),
                }
                for chunk in chunks
            ]
        }
        return json.dumps(payload, ensure_ascii=False)

    @tool
    async def search_academic_calendar(query: str, filters: dict[str, Any] | None = None) -> str:
        """Tìm thông tin về lịch học, học kỳ, deadline add/drop, kỳ thi và ngày nghỉ."""

        return await _search(
            query=query,
            filters=filters,
            enforced_filters={"category": "academic", "subcategory": "calendar"},
        )

    @tool
    async def search_policy_documents(query: str, filters: dict[str, Any] | None = None) -> str:
        """Tìm quy định, hướng dẫn và quyền/nghĩa vụ sinh viên trong tài liệu chính sách."""

        return await _search(
            query=query,
            filters=filters,
            enforced_filters={"category": "student_affairs"},
        )

    @tool
    async def search_financial_regulations(query: str, filters: dict[str, Any] | None = None) -> str:
        """Tìm học phí, tariff, lệ phí, phạt và thông tin tài chính dành cho sinh viên."""

        return await _search(
            query=query,
            filters=filters,
            enforced_filters={"category": "student_affairs", "subcategory": "financial"},
        )

    @tool
    async def search_vinuni(query: str, filters: dict[str, Any] | None = None) -> str:
        """Tìm kiếm tổng quát trên toàn bộ tài liệu công khai của VinUni.

        Dùng cho thư viện, phòng đăng ký (registrar), đời sống sinh viên, dịch vụ sinh
        viên và mọi câu hỏi không thuộc riêng lịch học, chính sách hay tài chính. Không
        áp đặt bộ lọc category nên bao phủ được toàn bộ corpus.
        """

        return await _search(query=query, filters=filters)

    @tool
    async def get_source_detail(source_id_or_url: str) -> str:
        """Lấy các đoạn liên quan nhất từ một nguồn cụ thể theo URL hoặc source id."""

        chunks = await retriever.search(
            query=source_id_or_url,
            filters={"source_url": source_id_or_url} if source_id_or_url.startswith("http") else None,
            limit=5,
        )
        payload = {
            "results": [
                {
                    "text": excerpt(chunk.text, max_chars=1200),
                    "score": chunk.score,
                    "metadata": chunk.metadata.model_dump(),
                }
                for chunk in chunks
            ]
        }
        return json.dumps(payload, ensure_ascii=False)

    return [
        search_academic_calendar,
        search_policy_documents,
        search_financial_regulations,
        search_vinuni,
        get_source_detail,
    ]

