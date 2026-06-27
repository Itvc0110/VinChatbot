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
from vinchatbot.app.repositories.forum import LOCKED

USER_ID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
OTHER_USER_ID = uuid.UUID("99999999-9999-9999-9999-999999999999")
ADMIN_ID = uuid.UUID("88888888-8888-8888-8888-888888888888")
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


def _other_student_user() -> AuthenticatedUser:
    return AuthenticatedUser(
        id=OTHER_USER_ID,
        email="student.business.demo@vinuni.edu.vn",
        full_name="Demo Business Student",
        preferred_name="Business Student",
        status="active",
        roles=("student",),
    )


def _admin_user() -> AuthenticatedUser:
    return AuthenticatedUser(
        id=ADMIN_ID,
        email="admin.global.demo@vinuni.edu.vn",
        full_name="Demo Global Admin",
        preferred_name="Global Admin",
        status="active",
        roles=("global_admin",),
    )


def _comment(**overrides: Any) -> dict[str, Any]:
    data = {
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
    data.update(overrides)
    return data


def _topic(*, comments: list[dict[str, Any]] | None = None, **overrides: Any) -> dict[str, Any]:
    data = {
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
        "deleted": False,
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
    data.update(overrides)
    return data


def _topic_state(topic: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": topic["id"],
        "author_user_id": topic["author_user_id"],
        "is_locked": topic["is_locked"],
        "deleted": topic["deleted"],
    }


def _comment_state(comment: dict[str, Any], topic: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": comment["id"],
        "topic_id": comment["topic_id"],
        "author_user_id": comment["author_user_id"],
        "deleted": comment["deleted"],
        "topic_is_locked": topic["is_locked"],
        "topic_deleted": topic["deleted"],
    }


class FakeForumRepository:
    def __init__(self, *, empty: bool = False, locked: bool = False) -> None:
        self.empty = empty
        self.topic = _topic(is_locked=locked, comments=[_comment()])
        self.comment = _comment()

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
        if self.empty or self.topic["deleted"]:
            return []
        return [self.topic]

    async def get_topic(self, **kwargs: Any) -> dict[str, Any] | None:
        include_deleted = kwargs.get("include_deleted", False)
        if kwargs["topic_id"] == MISSING_TOPIC_ID or self.empty:
            return None
        if self.topic["deleted"] and not include_deleted:
            return None
        return {**self.topic, "comments": [self.comment]}

    async def list_comments(self, **kwargs: Any) -> list[dict[str, Any]] | None:
        if kwargs["topic_id"] == MISSING_TOPIC_ID or self.empty:
            return None
        return [self.comment]

    async def get_topic_state(self, topic_id: uuid.UUID) -> dict[str, Any] | None:
        if topic_id == MISSING_TOPIC_ID or self.empty:
            return None
        return _topic_state(self.topic)

    async def get_comment_state(self, comment_id: uuid.UUID) -> dict[str, Any] | None:
        if comment_id != COMMENT_ID or self.empty:
            return None
        return _comment_state(self.comment, self.topic)

    async def create_topic(self, *, author_user_id: uuid.UUID, request: Any) -> dict[str, Any]:
        self.topic = _topic(
            author_user_id=author_user_id,
            title=request.title,
            content=request.content,
            is_pinned=False,
            comments=[],
        )
        return self.topic

    async def add_comment(self, *, author_user_id: uuid.UUID, request: Any, **_kwargs: Any):
        if self.topic["deleted"]:
            return None
        if self.topic["is_locked"]:
            return LOCKED
        self.comment = _comment(author_user_id=author_user_id, content=request.content)
        return self.comment

    async def patch_topic(
        self,
        *,
        request: Any,
        include_deleted: bool = False,
        **_kwargs: Any,
    ) -> dict[str, Any] | None:
        for field in request.model_fields_set:
            if field in self.topic:
                self.topic[field] = getattr(request, field)
        if self.topic["deleted"] and not include_deleted:
            return None
        return {**self.topic, "comments": [self.comment]}

    async def patch_comment(self, *, request: Any, **_kwargs: Any) -> dict[str, Any] | None:
        for field in request.model_fields_set:
            if field in self.comment:
                self.comment[field] = getattr(request, field)
        return self.comment


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
    user: AuthenticatedUser | None = None,
) -> FastAPI:
    app = FastAPI()
    app.include_router(forum_router)

    if authenticated:

        async def fake_current_user():
            return user or _student_user()

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


async def _post(path: str, app: FastAPI, json: dict[str, Any] | None = None):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.post(path, json=json)


async def _patch(path: str, app: FastAPI, json: dict[str, Any]):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.patch(path, json=json)


async def _delete(path: str, app: FastAPI):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.delete(path)


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


def test_forum_anonymous_create_topic_returns_401():
    response = _run(
        _post(
            "/forum/topics",
            _forum_app(FakeForumRepository(), authenticated=False),
            {
                "category_slug": "academic-qa",
                "title": "How do I prepare?",
                "content": "What should I check before add/drop?",
            },
        )
    )

    assert response.status_code == 401


def test_student_can_create_topic():
    response = _run(
        _post(
            "/forum/topics",
            _forum_app(FakeForumRepository()),
            {
                "category_slug": "academic-qa",
                "title": "  How do I prepare?  ",
                "content": "  What should I check before add/drop?  ",
            },
        )
    )

    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "How do I prepare?"
    assert body["content"] == "What should I check before add/drop?"


def test_student_can_comment_on_open_topic():
    response = _run(
        _post(
            f"/forum/topics/{TOPIC_ID}/comments",
            _forum_app(FakeForumRepository()),
            {"content": "  This is helpful.  "},
        )
    )

    assert response.status_code == 200
    assert response.json()["content"] == "This is helpful."


def test_student_cannot_comment_on_locked_topic():
    response = _run(
        _post(
            f"/forum/topics/{TOPIC_ID}/comments",
            _forum_app(FakeForumRepository(locked=True)),
            {"content": "Can I still reply?"},
        )
    )

    assert response.status_code == 403


def test_student_can_edit_own_topic_and_comment():
    app = _forum_app(FakeForumRepository())

    topic_response = _run(
        _patch(
            f"/forum/topics/{TOPIC_ID}",
            app,
            {"title": "Updated topic title", "content": "Updated topic body"},
        )
    )
    comment_response = _run(
        _patch(
            f"/forum/comments/{COMMENT_ID}",
            app,
            {"content": "Updated comment body"},
        )
    )

    assert topic_response.status_code == 200
    assert topic_response.json()["title"] == "Updated topic title"
    assert comment_response.status_code == 200
    assert comment_response.json()["content"] == "Updated comment body"


def test_student_cannot_edit_another_users_topic_or_comment():
    app = _forum_app(FakeForumRepository(), user=_other_student_user())

    topic_response = _run(
        _patch(
            f"/forum/topics/{TOPIC_ID}",
            app,
            {"title": "Not mine", "content": "Not mine"},
        )
    )
    comment_response = _run(
        _patch(f"/forum/comments/{COMMENT_ID}", app, {"content": "Not mine"})
    )

    assert topic_response.status_code == 403
    assert comment_response.status_code == 403


def test_student_can_soft_delete_own_topic_and_comment():
    topic_repo = FakeForumRepository()
    comment_repo = FakeForumRepository()

    topic_response = _run(_delete(f"/forum/topics/{TOPIC_ID}", _forum_app(topic_repo)))
    comment_response = _run(
        _delete(f"/forum/comments/{COMMENT_ID}", _forum_app(comment_repo))
    )

    assert topic_response.status_code == 204
    assert topic_repo.topic["deleted"] is True
    assert comment_response.status_code == 204
    assert comment_repo.comment["deleted"] is True


def test_admin_can_pin_lock_and_archive_topic():
    repo = FakeForumRepository()
    app = _forum_app(repo, user=_admin_user())

    pin_response = _run(_post(f"/forum/topics/{TOPIC_ID}/pin", app))
    lock_response = _run(_post(f"/forum/topics/{TOPIC_ID}/lock", app))
    archive_response = _run(_post(f"/forum/topics/{TOPIC_ID}/archive", app))

    assert pin_response.status_code == 200
    assert pin_response.json()["is_pinned"] is True
    assert lock_response.status_code == 200
    assert lock_response.json()["is_locked"] is True
    assert archive_response.status_code == 200
    assert archive_response.json()["id"] == str(TOPIC_ID)
    assert repo.topic["deleted"] is True


def test_admin_can_hide_and_unhide_comment():
    repo = FakeForumRepository()
    app = _forum_app(repo, user=_admin_user())

    hide_response = _run(_post(f"/forum/comments/{COMMENT_ID}/hide", app))
    unhide_response = _run(_post(f"/forum/comments/{COMMENT_ID}/unhide", app))

    assert hide_response.status_code == 200
    assert hide_response.json()["deleted"] is True
    assert unhide_response.status_code == 200
    assert unhide_response.json()["deleted"] is False


def test_archived_topic_is_hidden_from_student_list():
    repo = FakeForumRepository()
    app = _forum_app(repo, user=_admin_user())

    archive_response = _run(_post(f"/forum/topics/{TOPIC_ID}/archive", app))
    topics_response = _run(_get("/forum/topics", _forum_app(repo)))

    assert archive_response.status_code == 200
    assert topics_response.status_code == 200
    assert topics_response.json() == []


def test_forum_blank_title_and_comment_body_validation():
    app = _forum_app(FakeForumRepository())

    topic_response = _run(
        _post(
            "/forum/topics",
            app,
            {"category_slug": "academic-qa", "title": "   ", "content": "Body"},
        )
    )
    comment_response = _run(
        _post(f"/forum/topics/{TOPIC_ID}/comments", app, {"content": "   "})
    )

    assert topic_response.status_code == 422
    assert comment_response.status_code == 422


def test_forum_missing_topic_and_comment_writes_return_404():
    app = _forum_app(FakeForumRepository())

    topic_response = _run(
        _patch(
            f"/forum/topics/{MISSING_TOPIC_ID}",
            app,
            {"title": "Missing", "content": "Missing"},
        )
    )
    comment_response = _run(
        _patch(
            f"/forum/comments/{MISSING_TOPIC_ID}",
            app,
            {"content": "Missing"},
        )
    )

    assert topic_response.status_code == 404
    assert comment_response.status_code == 404


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
