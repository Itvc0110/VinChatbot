from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from vinchatbot.app.api.ratelimit import add_rate_limit_middleware
from vinchatbot.app.api.routes_auth import router as auth_router
from vinchatbot.app.api.routes_chat import router as chat_router
from vinchatbot.app.api.routes_health import router as health_router
from vinchatbot.app.api.routes_ingest import router as ingest_router
from vinchatbot.app.api.routes_students import router as students_router
from vinchatbot.app.api.routes_tickets import router as tickets_router
from vinchatbot.app.core.config import get_settings
from vinchatbot.app.core.logging import configure_logging
from vinchatbot.app.core.observability import add_request_id_middleware
from vinchatbot.app.db.connection import close_app_db_pool, open_app_db_pool


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        await open_app_db_pool(settings)
        try:
            yield
        finally:
            await close_app_db_pool()

    app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)

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
    app.include_router(auth_router)
    app.include_router(students_router)
    app.include_router(tickets_router)
    app.include_router(health_router)
    app.include_router(ingest_router)
    return app


app = create_app()
