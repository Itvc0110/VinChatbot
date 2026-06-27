from __future__ import annotations

import asyncio
import uuid

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from psycopg.errors import UndefinedTable

from vinchatbot.app.api.routes_forum import get_forum_repository
from vinchatbot.app.api.routes_forum import router as forum_router
from vinchatbot.app.dependencies.auth import get_current_user
from vinchatbot.app.repositories.auth import AuthenticatedUser

USER_ID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
TOPIC_ID = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")


def _run(awaitable):
    return asyncio.run(asyncio.wait_for(awaitable, timeout=2.0))


def _student_user() -> AuthenticatedUser:
    return AuthenticatedUser(
        id=USER_ID,
        email="student.cs.demo@vinuni.edu.vn",
        full_name="Demo CECS Student",
        preferred_name="CECS Student",
        status="active",
        roles=("student",),
    )


class MissingForumSchemaRepository:
    async def list_categories(self):
        raise UndefinedTable("forum_categories")

    async def list_topics(self, **_kwargs):
        raise UndefinedTable("forum_topics")

    async def get_topic(self, **_kwargs):
        raise UndefinedTable("forum_topics")

    async def create_topic(self, **_kwargs):
        raise UndefinedTable("forum_topics")


def _forum_app(repository: MissingForumSchemaRepository | None = None) -> FastAPI:
    app = FastAPI()
    app.include_router(forum_router)

    async def fake_current_user():
        return _student_user()

    app.dependency_overrides[get_current_user] = fake_current_user

    if repository is not None:

        async def fake_forum_repository():
            return repository

        app.dependency_overrides[get_forum_repository] = fake_forum_repository

    return app


async def _get(path: str, app: FastAPI):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.get(path)


async def _post(path: str, app: FastAPI, json: dict):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.post(path, json=json)


def test_forum_categories_return_controlled_error_when_schema_missing():
    response = _run(_get("/forum/categories", _forum_app(MissingForumSchemaRepository())))

    assert response.status_code == 503
    assert "Forum database schema is not available" in response.json()["detail"]


def test_forum_topics_return_controlled_error_when_schema_missing():
    response = _run(_get("/forum/topics", _forum_app(MissingForumSchemaRepository())))

    assert response.status_code == 503
    assert "UndefinedTable" not in response.text


def test_forum_topic_detail_returns_controlled_error_when_schema_missing():
    response = _run(
        _get(f"/forum/topics/{TOPIC_ID}", _forum_app(MissingForumSchemaRepository()))
    )

    assert response.status_code == 503
    assert "UndefinedTable" not in response.text


def test_forum_create_topic_returns_controlled_error_when_schema_missing():
    response = _run(
        _post(
            "/forum/topics",
            _forum_app(MissingForumSchemaRepository()),
            {
                "category_slug": "general",
                "title": "How do I find advising hours?",
                "content": "Where can I find advising hours for CECS students?",
            },
        )
    )

    assert response.status_code == 503
    assert "UndefinedTable" not in response.text
