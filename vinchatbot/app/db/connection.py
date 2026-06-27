from __future__ import annotations

from typing import TYPE_CHECKING

from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

if TYPE_CHECKING:
    from vinchatbot.app.core.config import Settings

_app_db_pool: AsyncConnectionPool | None = None


def _app_database_url(settings: Settings) -> str | None:
    return settings.app_database_url_pooled or settings.app_database_url_direct


async def open_app_db_pool(settings: Settings) -> AsyncConnectionPool | None:
    """Open the application database pool if an app DB URL is configured.

    Missing app DB configuration is valid for offline tests and local workflows that do not touch
    `/health/db`; the endpoint itself reports that state as unavailable.
    """

    global _app_db_pool

    if _app_db_pool is not None:
        return _app_db_pool

    conninfo = _app_database_url(settings)
    if not conninfo:
        return None

    min_size = max(0, int(settings.app_database_pool_min_size))
    max_size = max(min_size or 1, int(settings.app_database_pool_max_size))
    pool = AsyncConnectionPool(
        conninfo,
        kwargs={"autocommit": True, "row_factory": dict_row},
        min_size=min_size,
        max_size=max_size,
        open=False,
        name="app-db",
    )
    await pool.open(wait=False)
    _app_db_pool = pool
    return pool


async def close_app_db_pool() -> None:
    """Close the application database pool if it was opened."""

    global _app_db_pool

    pool = _app_db_pool
    _app_db_pool = None
    if pool is not None:
        await pool.close()


def get_app_db_pool() -> AsyncConnectionPool | None:
    return _app_db_pool
