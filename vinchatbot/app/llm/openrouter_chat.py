from __future__ import annotations

from vinchatbot.app.core.cache import install_llm_cache
from vinchatbot.app.core.config import Settings, get_settings
from vinchatbot.app.core.observability import get_langfuse_callbacks


def build_chat_model(
    settings: Settings | None = None,
    model: str | None = None,
    temperature: float | None = None,
):
    """Build a LangChain chat model backed by OpenRouter.

    `model` overrides the default chat model (e.g. a cheaper model for the guard tier).
    `temperature` overrides sampling (None → 0.1). Deterministic call sites — query expansion, intent
    routing, answer generation — pass 0.0 so the same question yields the same answer (Phase 1.11).
    """

    settings = settings or get_settings()
    # Mass cache (A2c): install the global exact-match LLM cache once (idempotent, fail-open). Done here so
    # BOTH the API server and the eval/script paths get it (run_eval never touches create_app).
    install_llm_cache(settings)
    if not settings.openrouter_api_key:
        raise RuntimeError("OPENROUTER_API_KEY is required to create the chat model.")

    try:
        from langchain_openai import ChatOpenAI
    except ImportError as exc:
        raise RuntimeError("Install langchain-openai to use OpenRouter chat models.") from exc

    headers = {}
    if settings.openrouter_app_referer:
        headers["HTTP-Referer"] = settings.openrouter_app_referer
    if settings.openrouter_app_title:
        headers["X-OpenRouter-Title"] = settings.openrouter_app_title

    return ChatOpenAI(
        model=model or settings.openrouter_chat_model,
        api_key=settings.openrouter_api_key,
        base_url=settings.openrouter_base_url,
        default_headers=headers or None,
        temperature=0.1 if temperature is None else temperature,
        # Fail-fast on a stalled connection + a couple retries (Phase 1.33): the OpenAI SDK defaults to a 600s
        # timeout, so without these one hung OpenRouter call freezes the turn (and blocks a fan-out gather).
        timeout=settings.llm_request_timeout_s,
        max_retries=settings.llm_max_retries,
        # Langfuse tracing (fail-open: [] -> None when disabled). Attaching at the model captures
        # every LLM call — supervisor, specialists, query expansion, guard, capability replies.
        callbacks=get_langfuse_callbacks(settings) or None,
    )

