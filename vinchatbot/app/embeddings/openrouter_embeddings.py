from __future__ import annotations

from langchain_core.embeddings import Embeddings

from vinchatbot.app.core.config import Settings, get_settings


class FastEmbedDenseEmbeddings(Embeddings):
    """LangChain-compatible dense embeddings backed by a local fastembed model (Phase 1.14).

    No API key, no per-query cost, deterministic. For E5-family models we apply the required
    "query:" / "passage:" prefixes (asymmetric retrieval); other models are embedded verbatim.
    The model is loaded lazily on first use so importing this module stays cheap.
    """

    def __init__(self, model_name: str) -> None:
        self.model_name = model_name
        self._is_e5 = "e5" in model_name.lower()
        self._model = None

    def _ensure_model(self):
        if self._model is None:
            try:
                from fastembed import TextEmbedding
            except ImportError as exc:  # pragma: no cover - dependency guard
                raise RuntimeError("Install fastembed to use the local embedding backend.") from exc
            self._model = TextEmbedding(self.model_name)
        return self._model

    def _prefixed(self, texts: list[str], kind: str) -> list[str]:
        return [f"{kind}: {text}" for text in texts] if self._is_e5 else list(texts)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        model = self._ensure_model()
        return [list(vec) for vec in model.embed(self._prefixed(list(texts), "passage"))]

    def embed_query(self, text: str) -> list[float]:
        model = self._ensure_model()
        return [float(value) for value in next(iter(model.embed(self._prefixed([text], "query"))))]


def build_embeddings(settings: Settings | None = None) -> Embeddings:
    """Build the configured embedding backend (OpenRouter API or local fastembed)."""

    settings = settings or get_settings()
    if (settings.embedding_backend or "openrouter").lower() == "fastembed_local":
        return FastEmbedDenseEmbeddings(settings.local_embedding_model)

    if not settings.openrouter_api_key:
        raise RuntimeError("OPENROUTER_API_KEY is required to create embeddings.")

    try:
        from langchain_openai import OpenAIEmbeddings
    except ImportError as exc:
        raise RuntimeError("Install langchain-openai to use OpenRouter embeddings.") from exc

    headers = {}
    if settings.openrouter_app_referer:
        headers["HTTP-Referer"] = settings.openrouter_app_referer
    if settings.openrouter_app_title:
        headers["X-OpenRouter-Title"] = settings.openrouter_app_title

    model = settings.openrouter_embedding_model
    # Non-OpenAI models served via OpenRouter (e.g. intfloat/multilingual-e5-large, baai/bge-m3) expect
    # raw STRING inputs. LangChain's OpenAIEmbeddings defaults to tiktoken-tokenizing into integer
    # arrays (OpenAI-only) → those endpoints return "No embedding data received". Disable that path for
    # non-OpenAI models so we send strings; keep it for openai/text-embedding-* (efficient token batching).
    is_openai_native = model.startswith("openai/text-embedding")
    extra: dict[str, object] = {}
    if not is_openai_native:
        extra = {"check_embedding_ctx_length": False, "tiktoken_enabled": False}

    return OpenAIEmbeddings(
        model=model,
        api_key=settings.openrouter_api_key,
        base_url=settings.openrouter_base_url,
        default_headers=headers or None,
        **extra,
    )

