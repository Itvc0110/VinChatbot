from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from vinchatbot.app.core.config import Settings, get_settings
from vinchatbot.app.rag.context import (
    SectionSibling,
    apply_metadata_boosts,
    dedup_by_text,
    expand_to_parent_sections,
    reorder_for_long_context,
    select_dynamic_k,
)
from vinchatbot.app.rag.reranker import OpenRouterReranker
from vinchatbot.app.schemas.document import DocumentChunk, DocumentMetadata
from vinchatbot.app.storage.qdrant_store import (
    ensure_qdrant_payload_indexes,
    qdrant_location_kwargs,
)
from vinchatbot.app.storage.vector_metadata import restore_document_metadata


@dataclass(frozen=True)
class RetrievedChunk:
    text: str
    metadata: DocumentMetadata
    score: float | None = None


class Retriever(Protocol):
    async def search(
        self,
        query: str,
        filters: dict[str, Any] | None = None,
        limit: int = 8,
        reorder: bool = True,
        boost_hints: dict[str, Any] | None = None,
        expand_sections: bool = False,
    ) -> list[RetrievedChunk]:
        ...

    async def search_candidates(
        self,
        query: str,
        filters: dict[str, Any] | None = None,
        limit: int = 8,
    ) -> list[RetrievedChunk]:
        """Candidate pool for multi-query fusion: vector/BM25 order, deduped, NOT reranked."""
        ...

    async def rerank_fused(
        self,
        query: str,
        chunks: list[RetrievedChunk],
        limit: int = 8,
        boost_hints: dict[str, Any] | None = None,
        reorder: bool = True,
        expand_sections: bool = False,
    ) -> list[RetrievedChunk]:
        """Rerank an already-fused candidate list ONCE, then run the standard finalize tail."""
        ...


class InMemoryRetriever:
    """Small deterministic retriever used for tests and offline development."""

    def __init__(self, chunks: list[DocumentChunk]) -> None:
        self.chunks = chunks

    async def search(
        self,
        query: str,
        filters: dict[str, Any] | None = None,
        limit: int = 8,
        reorder: bool = True,
        boost_hints: dict[str, Any] | None = None,
        expand_sections: bool = False,
    ) -> list[RetrievedChunk]:
        filters = filters or {}
        terms = {term.lower() for term in query.split() if len(term) > 1}
        scored: list[RetrievedChunk] = []
        for chunk in self.chunks:
            metadata = chunk.metadata.model_dump()
            if any(metadata.get(key) != value for key, value in filters.items()):
                continue
            text_lower = chunk.text.lower()
            score = sum(1 for term in terms if term in text_lower)
            if score > 0:
                scored.append(RetrievedChunk(chunk.text, chunk.metadata, float(score)))
        scored.sort(key=lambda item: item.score or 0.0, reverse=True)
        return scored[:limit]

    async def search_candidates(
        self,
        query: str,
        filters: dict[str, Any] | None = None,
        limit: int = 8,
    ) -> list[RetrievedChunk]:
        return await self.search(query, filters=filters, limit=limit, reorder=False)

    async def rerank_fused(
        self,
        query: str,
        chunks: list[RetrievedChunk],
        limit: int = 8,
        boost_hints: dict[str, Any] | None = None,
        reorder: bool = True,
        expand_sections: bool = False,
    ) -> list[RetrievedChunk]:
        return list(chunks)[:limit]


class QdrantHybridRetriever:
    def __init__(self, settings: Settings | None = None, vector_store=None) -> None:
        self.settings = settings or get_settings()
        self.backend = self.settings.vector_store_backend.lower().strip()
        self.vector_store = vector_store or self._build_vector_store()
        self.reranker = OpenRouterReranker(self.settings)

    def _build_vector_store(self):
        if self.backend == "qdrant":
            return self._build_qdrant_vector_store()
        if self.backend == "chroma":
            return self._build_chroma_vector_store()
        if self.backend == "pinecone":
            return self._build_pinecone_vector_store()
        raise RuntimeError(
            f"Unsupported VECTOR_STORE_BACKEND={self.settings.vector_store_backend!r}. "
            "Use qdrant, chroma, or pinecone."
        )

    def _build_qdrant_vector_store(self):
        try:
            from langchain_qdrant import FastEmbedSparse, QdrantVectorStore, RetrievalMode
        except ImportError as exc:
            raise RuntimeError("Install langchain-qdrant and fastembed to use Qdrant retrieval.") from exc

        from vinchatbot.app.embeddings.openrouter_embeddings import build_embeddings

        kwargs: dict[str, Any] = {
            "collection_name": self.settings.qdrant_collection,
            "embedding": build_embeddings(self.settings),
            "sparse_embedding": FastEmbedSparse(model_name="Qdrant/BM25"),
            "retrieval_mode": RetrievalMode.HYBRID,
        }
        kwargs.update(qdrant_location_kwargs(self.settings))
        vector_store = QdrantVectorStore.from_existing_collection(**kwargs)
        ensure_qdrant_payload_indexes(
            vector_store.client,
            self.settings.qdrant_collection,
            self.settings.qdrant_timeout_seconds,
        )
        return vector_store

    def _build_chroma_vector_store(self):
        try:
            from langchain_chroma import Chroma
        except ImportError as exc:
            raise RuntimeError(
                "Install optional Chroma dependencies with `python -m pip install -e \".[vector-backups]\"`."
            ) from exc

        from vinchatbot.app.embeddings.openrouter_embeddings import build_embeddings

        return Chroma(
            collection_name=self.settings.chroma_collection,
            persist_directory=self.settings.chroma_persist_dir,
            embedding_function=build_embeddings(self.settings),
        )

    def _build_pinecone_vector_store(self):
        try:
            from langchain_pinecone import PineconeVectorStore
        except ImportError as exc:
            raise RuntimeError(
                "Install optional Pinecone dependencies with `python -m pip install -e \".[vector-backups]\"`."
            ) from exc

        from vinchatbot.app.embeddings.openrouter_embeddings import build_embeddings

        kwargs: dict[str, Any] = {
            "index_name": self.settings.pinecone_index_name,
            "embedding": build_embeddings(self.settings),
        }
        if self.settings.pinecone_namespace:
            kwargs["namespace"] = self.settings.pinecone_namespace
        if self.settings.pinecone_api_key:
            kwargs["pinecone_api_key"] = self.settings.pinecone_api_key
        return PineconeVectorStore(**kwargs)

    async def search(
        self,
        query: str,
        filters: dict[str, Any] | None = None,
        limit: int = 8,
        reorder: bool = True,
        boost_hints: dict[str, Any] | None = None,
        expand_sections: bool = False,
    ) -> list[RetrievedChunk]:
        candidates = await self._fetch_candidates(query, filters, limit)
        if not candidates:
            return []
        return await self._finalize(
            query, candidates, limit, boost_hints, reorder, expand_sections=expand_sections
        )

    async def search_candidates(
        self,
        query: str,
        filters: dict[str, Any] | None = None,
        limit: int = 8,
    ) -> list[RetrievedChunk]:
        """Candidate pool for multi-query fusion: vector/BM25 order, deduped, NOT reranked. Lets
        the rerank-after-fusion path rerank once on the fused pool instead of once per variant."""
        candidates = await self._fetch_candidates(query, filters, limit)
        if self.settings.enable_result_dedup:
            candidates = dedup_by_text(candidates, lambda chunk: chunk.text)
        return candidates

    async def rerank_fused(
        self,
        query: str,
        chunks: list[RetrievedChunk],
        limit: int = 8,
        boost_hints: dict[str, Any] | None = None,
        reorder: bool = True,
        expand_sections: bool = False,
    ) -> list[RetrievedChunk]:
        """Rerank an already-fused candidate list ONCE, then run the standard finalize tail.

        `expand_sections=True` (point-lookups) stitches each kept chunk to its full section so the
        model reads the whole table/section and picks the exact row — while query expansion upstream
        still provides recall.
        """
        if not chunks:
            return []
        return await self._finalize(
            query, list(chunks), limit, boost_hints, reorder, expand_sections=expand_sections
        )

    async def _fetch_candidates(
        self,
        query: str,
        filters: dict[str, Any] | None,
        limit: int,
    ) -> list[RetrievedChunk]:
        """Vector/BM25 candidate fetch — no rerank, no post-processing (`score=None`)."""
        search_filter = self._to_qdrant_filter(filters or {}) if self.backend == "qdrant" else (filters or None)
        candidate_k = (
            max(self.settings.retrieval_candidate_k, limit)
            if self.settings.enable_dynamic_k
            else max(limit * 3, limit)
        )
        docs = await self.vector_store.asimilarity_search(query, k=candidate_k, filter=search_filter)
        return [
            RetrievedChunk(
                text=doc.page_content,
                metadata=restore_document_metadata(doc.metadata),
                score=None,
            )
            for doc in docs
        ]

    async def _finalize(
        self,
        query: str,
        chunks: list[RetrievedChunk],
        limit: int,
        boost_hints: dict[str, Any] | None,
        reorder: bool,
        expand_sections: bool = False,
    ) -> list[RetrievedChunk]:
        """Rerank the candidate pool, then dedup -> metadata-boost -> dynamic-k -> parent-doc ->
        lost-in-the-middle reorder. Shared by single-query `search()` and `rerank_fused()`."""
        if not chunks:
            return []

        # Rerank the whole candidate pool, then build a relevance-descending chunk list.
        reranked = await self.reranker.rerank(query, [chunk.text for chunk in chunks], top_n=len(chunks))
        if reranked:
            ranked = sorted(reranked, key=lambda item: item.score, reverse=True)
            ordered = [(chunks[item.index], item.score) for item in ranked if item.index < len(chunks)]
        else:
            ordered = [(chunk, chunk.score) for chunk in chunks]

        chunks = [
            RetrievedChunk(text=chunk.text, metadata=chunk.metadata, score=score)
            for chunk, score in ordered
        ]

        if self.settings.enable_result_dedup:
            chunks = dedup_by_text(chunks, lambda chunk: chunk.text)

        if self.settings.enable_metadata_boost:
            chunks = apply_metadata_boosts(chunks, query, hints=boost_hints, enabled=True)

        chunks = select_dynamic_k(
            chunks,
            lambda chunk: chunk.score,
            enabled=self.settings.enable_dynamic_k,
            min_k=self.settings.retrieval_min_k,
            max_k=max(self.settings.retrieval_max_k, limit) if not self.settings.enable_dynamic_k else self.settings.retrieval_max_k,
            ratio=self.settings.retrieval_score_ratio,
        )

        if (expand_sections or self.settings.enable_parent_doc) and self.backend == "qdrant":
            # Point-lookups (expand_sections) want the full section — incl. calendar tables — so they
            # bypass the calendar skip; the strict extraction prompt keeps the model from over-sharing.
            skip = (
                frozenset()
                if expand_sections
                else frozenset(
                    part.strip()
                    for part in (self.settings.parent_doc_skip_subcategories or "").split(",")
                    if part.strip()
                )
            )
            chunks = expand_to_parent_sections(
                chunks,
                self._fetch_section_siblings,
                max_chars=self.settings.parent_doc_max_chars,
                max_siblings=self.settings.parent_doc_max_siblings,
                skip_subcategories=skip,
            )

        if reorder and self.settings.enable_litm_reorder:
            chunks = reorder_for_long_context(chunks)
        return chunks

    def _fetch_section_siblings(self, parent_doc_id: str, section_id: str) -> list[SectionSibling]:
        """Return every chunk sharing `(parent_doc_id, section_id)` for parent-document
        retrieval. Scrolls the indexed `metadata.parent_doc_id` keyword field, then filters
        the section client-side (section_id is not separately indexed). Fails soft to []."""
        client = getattr(self.vector_store, "client", None)
        if client is None:
            return []
        try:
            from qdrant_client.models import FieldCondition, Filter, MatchValue
        except ImportError:
            return []
        scroll_filter = Filter(
            must=[FieldCondition(key="metadata.parent_doc_id", match=MatchValue(value=parent_doc_id))]
        )
        try:
            points, _next = client.scroll(
                collection_name=self.settings.qdrant_collection,
                scroll_filter=scroll_filter,
                limit=512,
                with_payload=True,
                with_vectors=False,
            )
        except Exception:
            return []
        siblings: list[SectionSibling] = []
        for point in points:
            payload = point.payload or {}
            metadata = payload.get("metadata") or {}
            if metadata.get("section_id") != section_id:
                continue
            text = payload.get("page_content") or ""
            if text:
                siblings.append((text, metadata.get("page_number"), metadata.get("content_hash")))
        return siblings

    @staticmethod
    def _to_qdrant_filter(filters: dict[str, Any]):
        if not filters:
            return None
        try:
            from qdrant_client.models import FieldCondition, Filter, MatchValue
        except ImportError as exc:
            raise RuntimeError("Install qdrant-client to use metadata filters.") from exc

        conditions = [
            FieldCondition(key=f"metadata.{key}", match=MatchValue(value=value))
            for key, value in filters.items()
            if value
        ]
        if not conditions:
            return None
        return Filter(must=conditions)

