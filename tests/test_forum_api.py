from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from psycopg.errors import UndefinedTable

from vinchatbot.app.api.routes_forum import get_forum_repository
from vinchatbot.app.api.routes_forum import router as forum_router
from vinchatbot.app.dependencies.auth import get_current_user
from vinchatbot.app.repositories.auth import AuthenticatedUser

USER_ID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
CATEGORY_ID = uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
TOPIC_ID = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
COMMENT_ID = uuid.UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")
MISSING_TOPIC_ID = uuid.UUID("eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee")
NOW = datetime(2026, 6, 27, 12, 0, tzinfo=UTC)


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


def _comment() -> dict[str, Any]:
    return {
        "id": COMMENT_ID,
        "topic_id": TOPIC_ID,
        "parent_comment_id": None,
        "author_user_id": USER_ID,
        "author_name": "CECS Student",
        "content": "Check your advising notes before add/drop week.",
        "is_official": False,
        "deleted": False,
        "score": 0,
        "my_vote": 0,
        "created_at": NOW,
        "updated_at": NOW,
        "replies": [],
    }


def _topic(*, comments: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {
        "id": TOPIC_ID,
        "category_id": CATEGORY_ID,
        "category_slug": "academic-qa",
        "category_name_en": "Academic Q&A",
        "category_name_vi": "Hỏi đáp học thuật",
        "author_user_id": USER_ID,
        "author_name": "CECS Student",
        "title": "How do I prepare for add/drop week?",
        "excerpt": "I am checking my Fall 2026 schedule.",
        "tags": ["registration"],
        "is_pinned": True,
        "is_locked": False,
        "has_official_answer": False,
        "view_count": 3,
        "comment_count": len(comments or []),
        "score": 1,
        "my_vote": 0,
        "created_at": NOW,
        "updated_at": NOW,
        "last_activity_at": NOW,
        "content": "I am checking my Fall 2026 schedule.",
        "attachments": [],
        "official_comment_id": None,
        "comments": comments or [],
    }


class FakeForumRepository:
    def __init__(self, *, empty: bool = False) -> None:
        self.empty = empty

    async def list_categories(self) -> list[dict[str, Any]]:
        if self.empty:
            return []
        return [
            {
                "id": CATEGORY_ID,
                "slug": "academic-qa",
                "name_en": "Academic Q&A",
                "name_vi": "Hỏi đáp học thuật",
                "description_en": "Questions about courses and advising.",
                "description_vi": "Câu hỏi về môn học và cố vấn.",
                "color": "#0b6bcb",
                "sort_order": 10,
                "is_active": True,
                "topic_count": 1,
            }
        ]

    async def list_topics(self, **_kwargs: Any) -> list[dict[str, Any]]:
        return [] if self.empty else [_topic()]

    async def get_topic(self, **kwargs: Any) -> dict[str, Any] | None:
        if kwargs["topic_id"] == MISSING_TOPIC_ID or self.empty:
            return None
        return _topic(comments=[_comment()])

    async def list_comments(self, **kwargs: Any) -> list[dict[str, Any]] | None:
        if kwargs["topic_id"] == MISSING_TOPIC_ID or self.empty:
            return None
        return [_comment()]


class MissingForumSchemaRepository:
    async def list_categories(self):
        raise UndefinedTable("forum_categories")

    async def list_topics(self, **_kwargs):
        raise UndefinedTable("forum_topics")

    async def get_topic(self, **_kwargs):
        raise UndefinedTable("forum_topics")

    async def list_comments(self, **_kwargs):
        raise UndefinedTable("forum_comments")


def _forum_app(
    repository: FakeForumRepository | MissingForumSchemaRepository | None = None,
    *,
    authenticated: bool = True,
) -> FastAPI:
    app = FastAPI()
    app.include_router(forum_router)

    if authenticated:

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


def test_forum_categories_returns_200():
    response = _run(_get("/forum/categories", _forum_app(FakeForumRepository())))

    assert response.status_code == 200
    body = response.json()
    assert body[0]["slug"] == "academic-qa"
    assert body[0]["topic_count"] == 1


def test_forum_topics_returns_200():
    response = _run(_get("/forum/topics", _forum_app(FakeForumRepository())))

    assert response.status_code == 200
    body = response.json()
    assert body[0]["id"] == str(TOPIC_ID)
    assert body[0]["title"] == "How do I prepare for add/drop week?"


def test_forum_topic_detail_returns_200_for_existing_topic():
    response = _run(_get(f"/forum/topics/{TOPIC_ID}", _forum_app(FakeForumRepository())))

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(TOPIC_ID)
    assert body["comments"][0]["id"] == str(COMMENT_ID)


def test_forum_topic_comments_returns_200():
    response = _run(
        _get(f"/forum/topics/{TOPIC_ID}/comments", _forum_app(FakeForumRepository()))
    )

    assert response.status_code == 200
    body = response.json()
    assert body[0]["id"] == str(COMMENT_ID)
    assert body[0]["topic_id"] == str(TOPIC_ID)


def test_forum_empty_state_returns_empty_arrays_not_500():
    app = _forum_app(FakeForumRepository(empty=True))

    categories = _run(_get("/forum/categories", app))
    topics = _run(_get("/forum/topics", app))

    assert categories.status_code == 200
    assert categories.json() == []
    assert topics.status_code == 200
    assert topics.json() == []


def test_forum_missing_topic_returns_404():
    app = _forum_app(FakeForumRepository())

    detail = _run(_get(f"/forum/topics/{MISSING_TOPIC_ID}", app))
    comments = _run(_get(f"/forum/topics/{MISSING_TOPIC_ID}/comments", app))

    assert detail.status_code == 404
    assert comments.status_code == 404


def test_forum_anonymous_request_returns_401():
    response = _run(
        _get("/forum/categories", _forum_app(FakeForumRepository(), authenticated=False))
    )

    assert response.status_code == 401


def test_forum_read_endpoints_return_controlled_error_when_schema_missing():
    app = _forum_app(MissingForumSchemaRepository())

    for path in [
        "/forum/categories",
        "/forum/topics",
        f"/forum/topics/{TOPIC_ID}",
        f"/forum/topics/{TOPIC_ID}/comments",
    ]:
        response = _run(_get(path, app))

        assert response.status_code == 503
        assert "Forum database schema is not available" in response.json()["detail"]
        assert "UndefinedTable" not in response.text
