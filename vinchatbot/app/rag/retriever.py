from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from vinchatbot.app.core.config import Settings, get_settings
from vinchatbot.app.rag.reranker import OpenRouterReranker
from vinchatbot.app.schemas.document import DocumentChunk, DocumentMetadata
from vinchatbot.app.storage.qdrant_store import ensure_qdrant_payload_indexes, qdrant_location_kwargs
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
    ) -> list[RetrievedChunk]:
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
    ) -> list[RetrievedChunk]:
        search_filter = self._to_qdrant_filter(filters or {}) if self.backend == "qdrant" else (filters or None)
        docs = await self.vector_store.asimilarity_search(
            query,
            k=max(limit * 3, limit),
            filter=search_filter,
        )
        if not docs:
            return []

        reranked = await self.reranker.rerank(query, [doc.page_content for doc in docs], top_n=limit)
        if reranked:
            ordered = [(docs[item.index], item.score) for item in reranked if item.index < len(docs)]
        else:
            ordered = [(doc, None) for doc in docs[:limit]]

        return [
            RetrievedChunk(
                text=doc.page_content,
                metadata=restore_document_metadata(doc.metadata),
                score=score,
            )
            for doc, score in ordered
        ]

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

