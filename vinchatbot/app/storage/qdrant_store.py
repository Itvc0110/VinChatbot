from __future__ import annotations

from typing import Any

from vinchatbot.app.core.config import Settings, get_settings


def build_sparse_embeddings():
    try:
        from langchain_qdrant import FastEmbedSparse
    except ImportError as exc:
        raise RuntimeError("Install langchain-qdrant and fastembed for sparse retrieval.") from exc
    return FastEmbedSparse(model_name="Qdrant/BM25")


def qdrant_location_kwargs(settings: Settings | None = None) -> dict[str, Any]:
    settings = settings or get_settings()
    if settings.qdrant_url:
        return {"url": settings.qdrant_url, "api_key": settings.qdrant_api_key}
    return {"path": settings.qdrant_local_path}

