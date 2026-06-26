from __future__ import annotations

import logging
from collections.abc import Iterable
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from vinchatbot.app.core.config import Settings, get_settings
from vinchatbot.app.schemas.document import DocumentChunk
from vinchatbot.app.storage.qdrant_store import (
    build_sparse_embeddings,
    ensure_qdrant_payload_indexes,
    qdrant_location_kwargs,
)
from vinchatbot.app.storage.vector_metadata import compact_vector_metadata

logger = logging.getLogger(__name__)

# Incremental ingest tuning. _SCROLL_PAGE_SIZE: ids fetched per scroll page (ids only, no payload/vectors).
# _DELETE_BATCH_SIZE: stale ids deleted per request.
_SCROLL_PAGE_SIZE = 10000
_DELETE_BATCH_SIZE = 2000
# Data-loss guard: a growth/maintenance re-crawl should delete only a little (a superset re-finds its old
# chunks; some churn is normal because chunk_id embeds the positional index, so an edited page re-chunks its
# tail). Abort when deletions exceed max(_FLOOR, _FRACTION × existing) — small enough to catch a partial/
# failed crawl or a changed hashing scheme (which drop a large fraction), large enough not to block a genuine
# growth crawl's normal edit churn. Use --recreate for an intentional full rebuild that drops many points.
_INCREMENTAL_DELETE_ABORT_FLOOR = 200
_INCREMENTAL_DELETE_ABORT_FRACTION = 0.10
# Above this many existing points, ZERO content-address overlap means the stored points were built with a
# different chunk_id hashing / embedding scheme → abort instead of mass re-embed + mass delete.
_INCREMENTAL_LARGE_COLLECTION = 100


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


def index_chunks(
    chunks: list[DocumentChunk],
    settings: Settings | None = None,
    recreate: bool = False,
    incremental: bool = False,
) -> int:
    if not chunks:
        return 0

    settings = settings or get_settings()
    backend = settings.vector_store_backend.lower().strip()
    if backend == "qdrant":
        return _index_qdrant_chunks(chunks, settings, recreate=recreate, incremental=incremental)
    if backend == "chroma":
        return _index_chroma_chunks(chunks, settings)
    if backend == "pinecone":
        return _index_pinecone_chunks(chunks, settings)
    raise RuntimeError(
        f"Unsupported VECTOR_STORE_BACKEND={settings.vector_store_backend!r}. "
        "Use qdrant, chroma, or pinecone."
    )


def _index_qdrant_chunks(
    chunks: list[DocumentChunk],
    settings: Settings,
    recreate: bool = False,
    incremental: bool = False,
) -> int:
    try:
        from langchain_qdrant import QdrantVectorStore, RetrievalMode
    except ImportError as exc:
        raise RuntimeError("Install langchain-qdrant to index chunks.") from exc

    from vinchatbot.app.embeddings.openrouter_embeddings import build_embeddings

    incremental = incremental or getattr(settings, "enable_incremental_ingest", False)

    documents = chunks_to_langchain_documents(chunks)
    ids = _qdrant_point_ids(chunks)
    parent_doc_ids = _parent_doc_ids(chunks)
    location_kwargs = qdrant_location_kwargs(settings)
    embedding = build_embeddings(settings)
    sparse_embedding = build_sparse_embeddings()

    collection_exists = _qdrant_collection_exists(settings.qdrant_collection, location_kwargs)
    if recreate and collection_exists:
        # Clean re-index: drop the collection so it is rebuilt from ONLY the current chunks. Removes
        # stale points accumulated across past ingests (Phase 1.13 prereq — the collection is never
        # otherwise cleared). Pair with QDRANT_COLLECTION=<scratch> to avoid touching production.
        _delete_qdrant_collection(settings.qdrant_collection, location_kwargs)
        collection_exists = False
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
        # Nothing to reuse on a fresh collection — incremental is a no-op (every chunk is embedded once).
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

    if incremental:
        return _incremental_upsert(
            vector_store,
            documents,
            ids,
            settings.qdrant_collection,
            settings.qdrant_batch_size,
            settings.qdrant_timeout_seconds,
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


def _incremental_upsert(
    vector_store: Any,
    documents: list[Any],
    ids: list[str],
    collection_name: str,
    batch_size: int,
    timeout_seconds: int | None,
) -> int:
    """Reconcile an EXISTING collection to the current full-corpus batch, re-embedding ONLY new chunks and
    deleting genuinely-stale points. Point ids are content-addressed (uuid5 of a content-hash chunk_id), so
    an id already present means an identical chunk is already embedded → skip it (reuse the stored vector).
    Chunks whose id is absent are embedded + upserted; points whose id is absent from the batch are stale.

    Returns the count of chunks actually embedded + added.

    Safety (this DELETES from a live collection):
    - ASSUMES `documents`/`ids` are the COMPLETE intended corpus (true for scripts/ingest_documents.py).
    - Cross-checks the scrolled id set against the collection's reported point count (an incomplete scroll
      would corrupt the guard math) and aborts on mismatch.
    - Aborts if there is ZERO content-address overlap with a large existing collection (the stored points
      use a different chunk_id/embedding scheme → reuse is invalid; use --recreate).
    - Aborts if it would delete more than `_INCREMENTAL_DELETE_ABORT_FLOOR` points — a growth/maintenance
      re-crawl should delete almost nothing, so a large stale set signals a partial/failed crawl. Use
      --recreate for an intentional full rebuild.

    Known limitation: the point id is derived from chunk TEXT (chunk_id = parent_doc_id:index:text), not the
    full stored payload. A chunk whose text is byte-identical but whose metadata changed (e.g. a re-stamped
    policy_code/date) keeps its id, is treated as unchanged, and retains its OLD payload. Run --recreate to
    fully reconcile payload metadata. (The default non-incremental path overwrites payloads every run.)
    """
    client = getattr(vector_store, "client", None)
    if client is None:
        raise RuntimeError("Qdrant vector store does not expose a client for incremental ingest.")

    # Idempotent: guarantees keyword payload indexes exist (covers fields added since the collection's build).
    _ensure_payload_indexes(vector_store, collection_name, timeout_seconds)

    existing_ids = _existing_point_ids(client, collection_name)
    reported_count = _collection_point_count(client, collection_name)
    if reported_count is None:
        logger.warning(
            "Incremental ingest could not read the collection point count for %s — skipping the "
            "scroll-completeness cross-check (the delete-floor + overlap guards still apply).",
            collection_name,
        )
    elif len(existing_ids) != reported_count:
        raise RuntimeError(
            f"Incremental ingest scrolled {len(existing_ids)} ids but the collection reports "
            f"{reported_count} points — the scroll was incomplete, so the safety guards cannot be trusted. "
            "Aborting (retry, or use --recreate)."
        )

    new_id_set = set(ids)
    overlap = len(existing_ids & new_id_set)
    to_add = [
        (doc, point_id)
        for doc, point_id in zip(documents, ids, strict=True)
        if point_id not in existing_ids
    ]
    to_delete = sorted(existing_ids - new_id_set)

    if len(existing_ids) > _INCREMENTAL_LARGE_COLLECTION and overlap == 0:
        raise RuntimeError(
            f"Incremental ingest found ZERO content-address overlap with the existing collection "
            f"({len(existing_ids)} points) — its points were built with a different chunk_id hashing or "
            "embedding scheme, so reusing vectors is invalid. Use --recreate for a clean rebuild."
        )
    delete_cap = max(
        _INCREMENTAL_DELETE_ABORT_FLOOR, int(_INCREMENTAL_DELETE_ABORT_FRACTION * len(existing_ids))
    )
    if len(to_delete) > delete_cap:
        raise RuntimeError(
            f"Incremental ingest would delete {len(to_delete)} of {len(existing_ids)} existing points "
            f"(cap {delete_cap}; overlap={overlap}, adding={len(to_add)}). A growth/maintenance re-crawl "
            "should delete only a little — this looks like a partial/failed crawl or a changed hashing "
            "scheme. Aborting to avoid data loss; re-run with --recreate for an intentional full rebuild."
        )

    if to_add:
        add_documents = [doc for doc, _ in to_add]
        add_ids = [point_id for _, point_id in to_add]
        try:
            vector_store.add_documents(add_documents, ids=add_ids, batch_size=batch_size)
        except Exception as exc:
            raise RuntimeError(f"Failed to upsert new chunks into Qdrant: {exc}") from exc
    if to_delete:
        _delete_point_ids(client, collection_name, to_delete, timeout_seconds)

    logger.info(
        "Incremental ingest collection=%s total=%s unchanged=%s added=%s deleted=%s overlap=%s",
        collection_name,
        len(ids),
        len(ids) - len(to_add),
        len(to_add),
        len(to_delete),
        overlap,
    )
    return len(to_add)


def _existing_point_ids(client: Any, collection_name: str) -> set[str]:
    ids: set[str] = set()
    next_offset = None
    while True:
        current_offset = next_offset
        points, next_offset = client.scroll(
            collection_name=collection_name,
            with_payload=False,
            with_vectors=False,
            limit=_SCROLL_PAGE_SIZE,
            offset=current_offset,
        )
        if not points:
            break
        for point in points:
            ids.add(str(point.id))
        # loop safety: stop on the last page (None) or a non-advancing offset (buggy/old server)
        if next_offset is None or next_offset == current_offset:
            break
    return ids


def _collection_point_count(client: Any, collection_name: str) -> int | None:
    """Authoritative point count for the scroll-completeness cross-check. None if unavailable (the
    delete-floor + overlap guards still protect; the cross-check is simply skipped)."""
    try:
        result = client.count(collection_name=collection_name, exact=True)
    except Exception:
        return None
    return getattr(result, "count", None)


def _delete_point_ids(
    client: Any, collection_name: str, point_ids: list[str], timeout_seconds: int | None
) -> None:
    try:
        from qdrant_client.models import PointIdsList
    except ImportError as exc:
        raise RuntimeError("Install qdrant-client to delete stale points.") from exc
    for start in range(0, len(point_ids), _DELETE_BATCH_SIZE):
        batch = point_ids[start : start + _DELETE_BATCH_SIZE]
        try:
            client.delete(
                collection_name=collection_name,
                points_selector=PointIdsList(points=batch),
                wait=True,
                timeout=timeout_seconds,
            )
        except Exception as exc:
            raise RuntimeError(f"Failed to delete stale Qdrant points: {exc}") from exc


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


def _delete_qdrant_collection(collection_name: str, location_kwargs: dict[str, Any]) -> None:
    try:
        from qdrant_client import QdrantClient
    except ImportError as exc:
        raise RuntimeError("Install qdrant-client to use Qdrant indexing.") from exc

    client = None
    try:
        client = QdrantClient(**location_kwargs)
        client.delete_collection(collection_name=collection_name)
    finally:
        if client is not None:
            client.close()


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

