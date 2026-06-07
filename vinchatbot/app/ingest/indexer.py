from __future__ import annotations

from collections.abc import Iterable

from vinchatbot.app.core.config import Settings, get_settings
from vinchatbot.app.schemas.document import DocumentChunk
from vinchatbot.app.storage.qdrant_store import build_sparse_embeddings, qdrant_location_kwargs


def chunks_to_langchain_documents(chunks: Iterable[DocumentChunk]):
    try:
        from langchain_core.documents import Document
    except ImportError as exc:
        raise RuntimeError("Install langchain-core to index documents.") from exc

    return [
        Document(page_content=chunk.text, metadata=chunk.to_langchain_metadata())
        for chunk in chunks
    ]


def index_chunks(chunks: list[DocumentChunk], settings: Settings | None = None) -> int:
    if not chunks:
        return 0

    settings = settings or get_settings()

    try:
        from langchain_qdrant import QdrantVectorStore, RetrievalMode
    except ImportError as exc:
        raise RuntimeError("Install langchain-qdrant to index chunks.") from exc

    from vinchatbot.app.embeddings.openrouter_embeddings import build_embeddings

    documents = chunks_to_langchain_documents(chunks)
    ids = [chunk.metadata.chunk_id for chunk in chunks]
    location_kwargs = qdrant_location_kwargs(settings)

    try:
        vector_store = QdrantVectorStore.from_existing_collection(
            collection_name=settings.qdrant_collection,
            embedding=build_embeddings(settings),
            sparse_embedding=build_sparse_embeddings(),
            retrieval_mode=RetrievalMode.HYBRID,
            **location_kwargs,
        )
        vector_store.add_documents(documents, ids=ids)
    except Exception:
        QdrantVectorStore.from_documents(
            documents,
            embedding=build_embeddings(settings),
            sparse_embedding=build_sparse_embeddings(),
            retrieval_mode=RetrievalMode.HYBRID,
            collection_name=settings.qdrant_collection,
            ids=ids,
            **location_kwargs,
        )
    return len(chunks)

