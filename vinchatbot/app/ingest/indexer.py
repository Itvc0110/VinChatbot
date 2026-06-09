from __future__ import annotations

from collections.abc import Iterable
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from vinchatbot.app.core.config import Settings, get_settings
from vinchatbot.app.schemas.document import DocumentChunk
from vinchatbot.app.storage.vector_metadata import compact_vector_metadata
from vinchatbot.app.storage.qdrant_store import (
    build_sparse_embeddings,
    ensure_qdrant_payload_indexes,
    qdrant_location_kwargs,
)


def chunks_to_langchain_documents(chunks: Iterable[DocumentChunk], compact_metadata: bool = False):
    try:
        from langchain_core.documents import Document
    except ImportError as exc:
        raise RuntimeError("Install langchain-core to index documents.") from exc

    return [
        Document(
            page_content=chunk.text,
            metadata=(
                compact_vector_metadata(chunk.metadata)
                if compact_metadata
                else chunk.to_langchain_metadata()
            ),
        )
        for chunk in chunks
    ]


def index_chunks(chunks: list[DocumentChunk], settings: Settings | None = None) -> int:
    if not chunks:
        return 0

    settings = settings or get_settings()
    backend = settings.vector_store_backend.lower().strip()
    if backend == "qdrant":
        return _index_qdrant_chunks(chunks, settings)
    if backend == "chroma":
        return _index_chroma_chunks(chunks, settings)
    if backend == "pinecone":
        return _index_pinecone_chunks(chunks, settings)
    raise RuntimeError(
        f"Unsupported VECTOR_STORE_BACKEND={settings.vector_store_backend!r}. "
        "Use qdrant, chroma, or pinecone."
    )


def _index_qdrant_chunks(chunks: list[DocumentChunk], settings: Settings) -> int:
    try:
        from langchain_qdrant import QdrantVectorStore, RetrievalMode
    except ImportError as exc:
        raise RuntimeError("Install langchain-qdrant to index chunks.") from exc

    from vinchatbot.app.embeddings.openrouter_embeddings import build_embeddings

    documents = chunks_to_langchain_documents(chunks)
    ids = _qdrant_point_ids(chunks)
    parent_doc_ids = _parent_doc_ids(chunks)
    location_kwargs = qdrant_location_kwargs(settings)
    embedding = build_embeddings(settings)
    sparse_embedding = build_sparse_embeddings()

    collection_exists = _qdrant_collection_exists(settings.qdrant_collection, location_kwargs)
    if collection_exists:
        try:
            vector_store = QdrantVectorStore.from_existing_collection(
                collection_name=settings.qdrant_collection,
                embedding=embedding,
                sparse_embedding=sparse_embedding,
                retrieval_mode=RetrievalMode.HYBRID,
                **location_kwargs,
            )
        except Exception as exc:
            raise RuntimeError(f"Qdrant collection is not available: {exc}") from exc
    else:
        return _create_qdrant_collection(
            documents=documents,
            ids=ids,
            settings=settings,
            embedding=embedding,
            sparse_embedding=sparse_embedding,
            retrieval_mode=RetrievalMode.HYBRID,
            location_kwargs=location_kwargs,
            qdrant_vector_store=QdrantVectorStore,
        )

    _delete_existing_parent_chunks(
        vector_store,
        settings.qdrant_collection,
        parent_doc_ids,
        settings.qdrant_timeout_seconds,
    )
    try:
        vector_store.add_documents(documents, ids=ids, batch_size=settings.qdrant_batch_size)
    except Exception as exc:
        raise RuntimeError(f"Failed to upsert chunks into Qdrant: {exc}") from exc
    return len(chunks)


def _create_qdrant_collection(
    *,
    documents: list[Any],
    ids: list[str],
    settings: Settings,
    embedding: Any,
    sparse_embedding: Any,
    retrieval_mode: Any,
    location_kwargs: dict[str, Any],
    qdrant_vector_store: Any,
) -> int:
    try:
        vector_store = qdrant_vector_store.from_documents(
            documents,
            embedding=embedding,
            sparse_embedding=sparse_embedding,
            retrieval_mode=retrieval_mode,
            collection_name=settings.qdrant_collection,
            ids=ids,
            batch_size=settings.qdrant_batch_size,
            **location_kwargs,
        )
    except Exception as exc:
        raise RuntimeError(f"Failed to create Qdrant collection: {exc}") from exc
    _ensure_payload_indexes(vector_store, settings.qdrant_collection, settings.qdrant_timeout_seconds)
    return len(documents)


def _index_chroma_chunks(chunks: list[DocumentChunk], settings: Settings) -> int:
    try:
        from langchain_chroma import Chroma
    except ImportError as exc:
        raise RuntimeError(
            "Install optional Chroma dependencies with `python -m pip install -e \".[vector-backups]\"`."
        ) from exc

    from vinchatbot.app.embeddings.openrouter_embeddings import build_embeddings

    documents = chunks_to_langchain_documents(chunks, compact_metadata=True)
    ids = [chunk.metadata.chunk_id for chunk in chunks]
    parent_doc_ids = _parent_doc_ids(chunks)
    vector_store = Chroma(
        collection_name=settings.chroma_collection,
        persist_directory=settings.chroma_persist_dir,
        embedding_function=build_embeddings(settings),
    )
    _delete_chroma_parent_chunks(vector_store, parent_doc_ids)
    vector_store.add_documents(documents, ids=ids)
    return len(chunks)


def _index_pinecone_chunks(chunks: list[DocumentChunk], settings: Settings) -> int:
    try:
        from langchain_pinecone import PineconeVectorStore
    except ImportError as exc:
        raise RuntimeError(
            "Install optional Pinecone dependencies with `python -m pip install -e \".[vector-backups]\"`."
        ) from exc

    from vinchatbot.app.embeddings.openrouter_embeddings import build_embeddings

    documents = chunks_to_langchain_documents(chunks, compact_metadata=True)
    ids = [chunk.metadata.chunk_id for chunk in chunks]
    parent_doc_ids = _parent_doc_ids(chunks)
    kwargs: dict[str, Any] = {
        "index_name": settings.pinecone_index_name,
        "embedding": build_embeddings(settings),
    }
    if settings.pinecone_namespace:
        kwargs["namespace"] = settings.pinecone_namespace
    if settings.pinecone_api_key:
        kwargs["pinecone_api_key"] = settings.pinecone_api_key
    vector_store = PineconeVectorStore(**kwargs)
    _delete_dense_parent_chunks(vector_store, parent_doc_ids)
    vector_store.add_documents(documents, ids=ids)
    return len(chunks)


def _parent_doc_ids(chunks: list[DocumentChunk]) -> list[str]:
    return sorted({chunk.metadata.parent_doc_id for chunk in chunks if chunk.metadata.parent_doc_id})


def _qdrant_point_ids(chunks: list[DocumentChunk]) -> list[str]:
    return [str(uuid5(NAMESPACE_URL, chunk.metadata.chunk_id)) for chunk in chunks]


def _qdrant_collection_exists(collection_name: str, location_kwargs: dict[str, Any]) -> bool:
    try:
        from qdrant_client import QdrantClient
    except ImportError as exc:
        raise RuntimeError("Install qdrant-client to use Qdrant indexing.") from exc

    client = None
    try:
        client = QdrantClient(**location_kwargs)
        client.get_collection(collection_name=collection_name)
        return True
    except Exception as exc:
        if _is_missing_collection_error(exc):
            return False
        raise RuntimeError(f"Qdrant collection is not available: {exc}") from exc
    finally:
        if client is not None:
            client.close()


def _delete_existing_parent_chunks(
    vector_store: Any,
    collection_name: str,
    parent_doc_ids: list[str],
    timeout_seconds: int | None,
) -> None:
    if not parent_doc_ids:
        return
    client = getattr(vector_store, "client", None)
    if client is None:
        raise RuntimeError("Qdrant vector store does not expose a client for document replacement.")
    try:
        from qdrant_client.models import FieldCondition, Filter, MatchValue
    except ImportError as exc:
        raise RuntimeError("Install qdrant-client to replace existing document chunks.") from exc

    _ensure_payload_indexes(vector_store, collection_name, timeout_seconds)
    for parent_doc_id in parent_doc_ids:
        points_selector = Filter(
            must=[
                FieldCondition(
                    key="metadata.parent_doc_id",
                    match=MatchValue(value=parent_doc_id),
                )
            ]
        )
        try:
            client.delete(
                collection_name=collection_name,
                points_selector=points_selector,
                wait=True,
                timeout=timeout_seconds,
            )
        except Exception as exc:
            raise RuntimeError(
                f"Failed to delete old Qdrant chunks for parent_doc_id={parent_doc_id}: {exc}"
            ) from exc


def _delete_chroma_parent_chunks(vector_store: Any, parent_doc_ids: list[str]) -> None:
    if not parent_doc_ids:
        return
    for parent_doc_id in parent_doc_ids:
        try:
            existing = vector_store.get(where={"parent_doc_id": parent_doc_id})
            ids = existing.get("ids", []) if isinstance(existing, dict) else []
            if ids:
                vector_store.delete(ids=ids)
        except Exception as exc:
            raise RuntimeError(
                f"Failed to delete old Chroma chunks for parent_doc_id={parent_doc_id}: {exc}"
            ) from exc


def _delete_dense_parent_chunks(vector_store: Any, parent_doc_ids: list[str]) -> None:
    if not parent_doc_ids or not hasattr(vector_store, "delete"):
        return
    for parent_doc_id in parent_doc_ids:
        try:
            vector_store.delete(filter={"parent_doc_id": parent_doc_id})
        except TypeError:
            vector_store.delete(where={"parent_doc_id": parent_doc_id})
        except Exception as exc:
            raise RuntimeError(
                f"Failed to delete old vector chunks for parent_doc_id={parent_doc_id}: {exc}"
            ) from exc


def _ensure_payload_indexes(
    vector_store: Any,
    collection_name: str,
    timeout_seconds: int | None,
) -> None:
    client = getattr(vector_store, "client", None)
    if client is None:
        raise RuntimeError("Qdrant vector store does not expose a client for payload indexing.")
    ensure_qdrant_payload_indexes(client, collection_name, timeout_seconds)


def _is_missing_collection_error(exc: Exception) -> bool:
    status_code = getattr(exc, "status_code", None)
    response = getattr(exc, "response", None)
    if status_code == 404 or getattr(response, "status_code", None) == 404:
        return True
    message = str(exc).lower()
    return (
        "collection not found" in message
        or ("collection " in message and " not found" in message)
        or "does not exist" in message
        or "doesn't exist" in message
        or "not found: collection" in message
        or "status code: 404" in message
    )

