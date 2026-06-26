from __future__ import annotations

import asyncio
from types import SimpleNamespace

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from psycopg.rows import dict_row

from vinchatbot.app.api import routes_health
from vinchatbot.app.db import connection as db_connection


def _run(awaitable):
    return asyncio.run(asyncio.wait_for(awaitable, timeout=2.0))


def _health_app() -> FastAPI:
    app = FastAPI()
    app.include_router(routes_health.router)
    return app


async def _get_db_health() -> tuple[int, dict]:
    transport = ASGITransport(app=_health_app())
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/health/db")
        return response.status_code, response.json()


def _db_settings(**overrides):
    base = {
        "app_database_url_direct": None,
        "app_database_url_pooled": None,
        "app_database_pool_min_size": 1,
        "app_database_pool_max_size": 5,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def test_db_health_returns_503_when_app_database_not_configured():
    _run(db_connection.close_app_db_pool())

    status_code, body = _run(_get_db_health())

    assert status_code == 503
    assert body["detail"] == {
        "status": "unavailable",
        "reason": "app database is not configured",
    }


def test_db_health_uses_pool_without_exposing_connection_details(monkeypatch):
    class FakeCursor:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def execute(self, _query):
            return None

        async def fetchone(self):
            return {
                "database": "neondb",
                "user": "app_user",
                "version": "PostgreSQL 17.x on neon",
            }

    class FakeConnection:
        def cursor(self):
            return FakeCursor()

    class FakeConnectionContext:
        async def __aenter__(self):
            return FakeConnection()

        async def __aexit__(self, exc_type, exc, tb):
            return None

    class FakePool:
        def connection(self):
            return FakeConnectionContext()

    monkeypatch.setattr(routes_health, "get_app_db_pool", lambda: FakePool())

    status_code, body = _run(_get_db_health())

    assert status_code == 200
    assert body["status"] == "ok"
    assert body["database"] == "neondb"
    assert body["user"] == "app_user"
    assert body["provider"] == "neon"
    assert isinstance(body["latency_ms"], float | int)
    assert "PostgreSQL" in body["version"]


def test_open_app_db_pool_is_noop_without_app_database_url():
    _run(db_connection.close_app_db_pool())

    pool = _run(db_connection.open_app_db_pool(_db_settings()))

    assert pool is None
    assert db_connection.get_app_db_pool() is None


def test_open_app_db_pool_prefers_pooled_url(monkeypatch):
    created = {}

    class FakePool:
        def __init__(self, conninfo, **kwargs):
            created["conninfo"] = conninfo
            created["kwargs"] = kwargs
            self.opened = False
            self.closed = False

        async def open(self, *, wait=False, timeout=30.0):
            created["open_wait"] = wait
            self.opened = True

        async def close(self, timeout=5.0):
            self.closed = True

    monkeypatch.setattr(db_connection, "AsyncConnectionPool", FakePool)
    _run(db_connection.close_app_db_pool())

    pool = _run(
        db_connection.open_app_db_pool(
            _db_settings(
                app_database_url_direct="postgresql://direct.example/neondb",
                app_database_url_pooled="postgresql://pooled.example/neondb",
                app_database_pool_min_size=2,
                app_database_pool_max_size=4,
            )
        )
    )

    assert pool is not None
    assert created["conninfo"] == "postgresql://pooled.example/neondb"
    assert created["kwargs"]["kwargs"] == {"autocommit": True, "row_factory": dict_row}
    assert created["kwargs"]["min_size"] == 2
    assert created["kwargs"]["max_size"] == 4
    assert created["kwargs"]["open"] is False
    assert created["open_wait"] is False

    _run(db_connection.close_app_db_pool())
