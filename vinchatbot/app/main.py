from __future__ import annotations

from fastapi import FastAPI

from vinchatbot.app.api.routes_chat import router as chat_router
from vinchatbot.app.api.routes_ingest import router as ingest_router
from vinchatbot.app.core.config import get_settings
from vinchatbot.app.core.logging import configure_logging


def create_app() -> FastAPI:
    configure_logging()
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version="0.1.0")

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

