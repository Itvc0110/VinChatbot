from __future__ import annotations

import logging
import time
from typing import Any

from fastapi import APIRouter, HTTPException, status

from vinchatbot.app.db.connection import get_app_db_pool

router = APIRouter(tags=["system"])
logger = logging.getLogger(__name__)


@router.get("/health/db")
async def database_health() -> dict[str, Any]:
    pool = get_app_db_pool()
    if pool is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "status": "unavailable",
                "reason": "app database is not configured",
            },
        )

    started = time.perf_counter()
    try:
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "select current_database() as database, current_user as user, version() as version"
                )
                row = await cur.fetchone()
    except Exception as exc:
        logger.warning("App database health check failed: %s", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "status": "unavailable",
                "reason": "app database is unreachable",
            },
        ) from exc

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "status": "unavailable",
                "reason": "app database returned no health row",
            },
        )

    latency_ms = round((time.perf_counter() - started) * 1000, 2)
    return {
        "status": "ok",
        "database": row["database"],
        "user": row["user"],
        "provider": "neon",
        "latency_ms": latency_ms,
        "version": row["version"],
    }
