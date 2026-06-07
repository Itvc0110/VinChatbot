from __future__ import annotations

from vinchatbot.app.core.config import Settings, get_settings


def build_chat_model(settings: Settings | None = None):
    """Build a LangChain chat model backed by OpenRouter."""

    settings = settings or get_settings()
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
        model=settings.openrouter_chat_model,
        api_key=settings.openrouter_api_key,
        base_url=settings.openrouter_base_url,
        default_headers=headers or None,
        temperature=0.1,
    )

