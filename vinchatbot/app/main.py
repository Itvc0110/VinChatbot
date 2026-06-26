from __future__ import annotations

from fastapi import FastAPI

from vinchatbot.app.api.ratelimit import add_rate_limit_middleware
from vinchatbot.app.api.routes_chat import router as chat_router
from vinchatbot.app.api.routes_ingest import router as ingest_router
from vinchatbot.app.core.config import get_settings
from vinchatbot.app.core.logging import configure_logging
from vinchatbot.app.core.observability import add_request_id_middleware


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings)
    app = FastAPI(title=settings.app_name, version="0.1.0")

    # Rate limiting (Phase 1.10). Registered before request_id so the request-id middleware (added
    # next) wraps it as the outer layer — throttled 429s still carry X-Request-ID for correlation.
    # No-op unless RATE_LIMIT_ENABLED. /health + OPTIONS are exempt.
    add_rate_limit_middleware(app, settings)

    add_request_id_middleware(app)

    @app.get("/health", tags=["system"])
    async def health() -> dict[str, str]:
        return {
            "status": "ok",
            "app": settings.app_name,
            "environment": settings.app_env,
        }

    app.include_router(chat_router)
    app.include_router(ingest_router)
    return app


app = create_app()
