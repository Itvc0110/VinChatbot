from __future__ import annotations

from typing import TYPE_CHECKING

from psycopg import AsyncConnection
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

if TYPE_CHECKING:
    from vinchatbot.app.core.config import Settings

_app_db_pool: AsyncConnectionPool | None = None
_app_db_pool_readonly: AsyncConnectionPool | None = None


async def _apply_readonly(conn: AsyncConnection) -> None:
    """Force this connection's transactions read-only at the Postgres session level, so the
    personalization DB tools can only SELECT — a write raises "cannot execute … in a read-only
    transaction" even without a dedicated read-only DB role. (Verified live: this blocks writes under
    autocommit too — PostgreSQL applies default_transaction_read_only to autocommit statements.)

    Uses a runtime ``SET`` rather than the ``-c default_transaction_read_only=on`` STARTUP option, which
    Neon's PgBouncer pooler rejects as an unsupported startup parameter.

    Wired as BOTH the pool's ``configure`` (once, at physical-connection creation) AND its ``reset``
    (on every return-to-pool), so the read-only GUC is re-applied on each reuse — robust even if a
    connection's session state is reset between borrows (e.g. a pooled/PgBouncer URL), not just on the
    preferred direct URL.
    """
    await conn.execute("SET default_transaction_read_only = on")


def _app_database_url(settings: Settings) -> str | None:
    return settings.app_database_url_pooled or settings.app_database_url_direct


def _readonly_database_url(settings: Settings) -> str | None:
    # Prefer a dedicated read-only role URL; otherwise the DIRECT (unpooled) URL, where the read-only
    # SET reliably persists for the life of the physical connection (no PgBouncer session reset between
    # transactions). Pooled is the last resort.
    return (
        settings.app_database_url_readonly
        or settings.app_database_url_direct
        or settings.app_database_url_pooled
    )


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


async def open_readonly_app_db_pool(settings: Settings) -> AsyncConnectionPool | None:
    """Open the dedicated READ-ONLY pool used by the personalization DB tools (Phase 5).

    Connects via the read-only role URL when configured, else the normal URL, and forces every
    transaction read-only at the session level. Sized lazily (min_size=0) so it adds no idle
    connections until a student actually asks a personal question. Missing DB config is valid offline.
    """

    global _app_db_pool_readonly

    if _app_db_pool_readonly is not None:
        return _app_db_pool_readonly

    conninfo = _readonly_database_url(settings)
    if not conninfo:
        return None

    max_size = max(1, int(settings.app_database_pool_max_size))
    pool = AsyncConnectionPool(
        conninfo,
        kwargs={"autocommit": True, "row_factory": dict_row},
        configure=_apply_readonly,  # set read-only when each physical connection is created
        reset=_apply_readonly,  # AND re-apply on every return-to-pool, so reuse can't lose it
        min_size=0,
        max_size=max_size,
        open=False,
        name="app-db-readonly",
    )
    await pool.open(wait=False)
    _app_db_pool_readonly = pool
    return pool


async def close_app_db_pool() -> None:
    """Close the application database pool(s) if they were opened."""

    global _app_db_pool, _app_db_pool_readonly

    pool = _app_db_pool
    readonly_pool = _app_db_pool_readonly
    _app_db_pool = None
    _app_db_pool_readonly = None
    if pool is not None:
        await pool.close()
    if readonly_pool is not None:
        await readonly_pool.close()


def get_app_db_pool() -> AsyncConnectionPool | None:
    return _app_db_pool


def get_readonly_app_db_pool() -> AsyncConnectionPool | None:
    return _app_db_pool_readonly
