from __future__ import annotations

import uuid

from fastapi import FastAPI, Request

from vinchatbot.app.api.routes_chat import router as chat_router
from vinchatbot.app.api.routes_ingest import router as ingest_router
from vinchatbot.app.core.config import get_settings
from vinchatbot.app.core.logging import configure_logging
from vinchatbot.app.core.observability import reset_request_id, set_request_id


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings)
    app = FastAPI(title=settings.app_name, version="0.1.0")

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        # Honor an inbound correlation id (e.g. from a gateway) or mint one; expose it on the
        # response and bind it to logs for this request. Fail-open: never block the request.
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        token = set_request_id(request_id)
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            reset_request_id(token)

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

