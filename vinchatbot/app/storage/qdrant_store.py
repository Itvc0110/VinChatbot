from __future__ import annotations

from typing import Any

from vinchatbot.app.core.config import Settings, get_settings

QDRANT_KEYWORD_PAYLOAD_FIELDS = (
    "metadata.parent_doc_id",
    "metadata.source_url",
    "metadata.document_type",
    "metadata.category",
    "metadata.subcategory",
    "metadata.academic_year",
    "metadata.term",
    "metadata.original_language",
    "metadata.source_kind",
    "metadata.source_trust",
    "metadata.policy_code",
    "metadata.event_type",
    "metadata.fee_type",
)


def build_sparse_embeddings():
    try:
        from langchain_qdrant import FastEmbedSparse
    except ImportError as exc:
        raise RuntimeError("Install langchain-qdrant and fastembed for sparse retrieval.") from exc
    return FastEmbedSparse(model_name="Qdrant/BM25")


def qdrant_location_kwargs(settings: Settings | None = None) -> dict[str, Any]:
    settings = settings or get_settings()
    kwargs: dict[str, Any] = {"timeout": settings.qdrant_timeout_seconds}
    if settings.qdrant_url:
        kwargs.update({"url": settings.qdrant_url, "api_key": settings.qdrant_api_key})
        return kwargs
    kwargs["path"] = settings.qdrant_local_path
    return kwargs


def ensure_qdrant_payload_indexes(
    client: Any,
    collection_name: str,
    timeout_seconds: int | None,
) -> None:
    try:
        from qdrant_client.models import PayloadSchemaType
    except ImportError as exc:
        raise RuntimeError("Install qdrant-client to create Qdrant payload indexes.") from exc

    for field_name in QDRANT_KEYWORD_PAYLOAD_FIELDS:
        try:
            client.create_payload_index(
                collection_name=collection_name,
                field_name=field_name,
                field_schema=PayloadSchemaType.KEYWORD,
                wait=True,
                timeout=timeout_seconds,
            )
        except Exception as exc:
            if _is_existing_payload_index_error(exc):
                continue
            raise RuntimeError(
                f"Failed to create Qdrant payload index for {field_name}: {exc}"
            ) from exc


def _is_existing_payload_index_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return any(
        marker in message
        for marker in [
            "already exists",
            "already has",
            "index exists",
            "same name already exists",
        ]
    )

