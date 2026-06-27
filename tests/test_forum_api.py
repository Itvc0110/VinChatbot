from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from psycopg.errors import UndefinedTable

from vinchatbot.app.api.routes_admin_notifications import get_admin_notification_repository
from vinchatbot.app.api.routes_forum import get_forum_repository
from vinchatbot.app.api.routes_forum import router as forum_router
from vinchatbot.app.dependencies.auth import get_current_user
from vinchatbot.app.repositories.auth import AuthenticatedUser
from vinchatbot.app.repositories.forum import LOCKED

USER_ID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
OTHER_USER_ID = uuid.UUID("99999999-9999-9999-9999-999999999999")
ADMIN_ID = uuid.UUID("88888888-8888-8888-8888-888888888888")
CATEGORY_ID = uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
CATEGORY_ID_TWO = uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccd")
TOPIC_ID = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
TOPIC_ID_TWO = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbc")
COMMENT_ID = uuid.UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")
MISSING_TOPIC_ID = uuid.UUID("eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee")
NOTIFICATION_ID = uuid.UUID("77777777-7777-7777-7777-777777777777")
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
        "author_roles": ["student"],
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
        "author_roles": ["student"],
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
    def __init__(
        self,
        *,
        empty: bool = False,
        locked: bool = False,
        topics: list[dict[str, Any]] | None = None,
        comment: dict[str, Any] | None = None,
    ) -> None:
        self.empty = empty
        self.comment = comment or _comment()
        self.topic = topics[0] if topics else _topic(is_locked=locked, comments=[self.comment])
        self.topics = topics or [self.topic]

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

    async def list_topics(self, **kwargs: Any) -> list[dict[str, Any]]:
        if self.empty:
            return []
        topics = list(self.topics)
        category_slug = kwargs.get("category_slug")
        category_id = kwargs.get("category_id")
        search = (kwargs.get("search") or "").strip().lower()
        include_deleted = kwargs.get("include_deleted", False)
        only_deleted = kwargs.get("only_deleted", False)
        if only_deleted:
            topics = [topic for topic in topics if topic["deleted"]]
        elif not include_deleted:
            topics = [topic for topic in topics if not topic["deleted"]]
        if category_slug:
            topics = [topic for topic in topics if topic["category_slug"] == category_slug]
        if category_id:
            topics = [topic for topic in topics if topic["category_id"] == category_id]
        if search:
            topics = [
                topic
                for topic in topics
                if search in topic["title"].lower()
                or search in str(topic.get("content") or "").lower()
            ]
        sort = kwargs.get("sort", "active")
        if sort in {"most_commented", "comments"}:
            topics.sort(
                key=lambda topic: (
                    not topic["is_pinned"],
                    -int(topic["comment_count"]),
                    -topic["last_activity_at"].timestamp(),
                )
            )
        elif sort == "new":
            topics.sort(
                key=lambda topic: (not topic["is_pinned"], -topic["created_at"].timestamp()),
            )
        else:
            topics.sort(
                key=lambda topic: (
                    not topic["is_pinned"],
                    -topic["last_activity_at"].timestamp(),
                ),
            )
        return topics

    async def get_topic(self, **kwargs: Any) -> dict[str, Any] | None:
        include_deleted = kwargs.get("include_deleted", False)
        if kwargs["topic_id"] == MISSING_TOPIC_ID or self.empty:
            return None
        topic = next((item for item in self.topics if item["id"] == kwargs["topic_id"]), None)
        if topic is None:
            return None
        if topic["deleted"] and not include_deleted:
            return None
        comments = list(topic.get("comments") or [self.comment])
        if not kwargs.get("include_deleted_comments", False):
            comments = [_hidden_comment_placeholder(comment) for comment in comments]
        return {**topic, "comments": comments}

    async def list_comments(self, **kwargs: Any) -> list[dict[str, Any]] | None:
        if kwargs["topic_id"] == MISSING_TOPIC_ID or self.empty:
            return None
        comments = [self.comment]
        if not kwargs.get("include_deleted_comments", False):
            comments = [_hidden_comment_placeholder(comment) for comment in comments]
        return comments

    async def get_topic_state(self, topic_id: uuid.UUID) -> dict[str, Any] | None:
        if topic_id == MISSING_TOPIC_ID or self.empty:
            return None
        topic = next((item for item in self.topics if item["id"] == topic_id), None)
        return _topic_state(topic) if topic else None

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
        self.topics = [self.topic]
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
        self.topics = [self.topic if topic["id"] == self.topic["id"] else topic for topic in self.topics]
        if self.topic["deleted"] and not include_deleted:
            return None
        return {**self.topic, "comments": [self.comment]}

    async def patch_comment(self, *, request: Any, **_kwargs: Any) -> dict[str, Any] | None:
        for field in request.model_fields_set:
            if field in self.comment:
                self.comment[field] = getattr(request, field)
        return self.comment


def _hidden_comment_placeholder(comment: dict[str, Any]) -> dict[str, Any]:
    if not comment.get("deleted"):
        return comment
    return {
        **comment,
        "author_name": None,
        "author_roles": [],
        "content": "[hidden by moderator]",
    }


class FakeForumNotificationRepository:
    def __init__(self) -> None:
        self.created: list[dict[str, Any]] = []

    async def list_target_institutes(self, _current_user: AuthenticatedUser):
        return [
            {
                "id": CATEGORY_ID,
                "code": "CECS",
                "name_vi": "CECS",
                "name_en": "CECS",
            }
        ]

    async def create_notification(self, *, current_user: AuthenticatedUser, request: Any):
        payload = request.model_dump()
        row = {
            "id": NOTIFICATION_ID,
            "type": payload["type"],
            "title": payload["title"],
            "message": payload["message"],
            "priority": payload["priority"],
            "status": payload["status"],
            "target_scope": payload["target_scope"],
            "institute_id": payload["institute_id"],
            "institute_code": None,
            "course_id": None,
            "course_code": None,
            "cohort": payload["cohort"],
            "deadline": payload["deadline"],
            "event_date": payload["event_date"],
            "start_date": payload["start_date"],
            "end_date": payload["end_date"],
            "source_title": payload["source_title"],
            "source_url": payload["source_url"],
            "forum_topic_id": payload["forum_topic_id"],
            "forum_comment_id": payload["forum_comment_id"],
            "created_by": current_user.id,
            "created_by_email": current_user.email,
            "created_by_name": current_user.full_name,
            "created_at": NOW,
            "updated_at": NOW,
        }
        self.created.append(row)
        return row


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
    notification_repository: FakeForumNotificationRepository | None = None,
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

    if notification_repository is not None:

        async def fake_notification_repository():
            return notification_repository

        app.dependency_overrides[get_admin_notification_repository] = fake_notification_repository

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


def test_forum_topics_support_search_title_and_body():
    repo = FakeForumRepository(
        topics=[
            _topic(title="Final exam preparation tips", content="Study plan"),
            _topic(
                id=TOPIC_ID_TWO,
                title="Campus printers",
                content="Portal login troubleshooting steps",
                is_pinned=False,
            ),
        ]
    )

    title_response = _run(_get("/forum/topics?search=final", _forum_app(repo)))
    body_response = _run(_get("/forum/topics?q=troubleshooting", _forum_app(repo)))

    assert title_response.status_code == 200
    assert [item["title"] for item in title_response.json()] == [
        "Final exam preparation tips"
    ]
    assert body_response.status_code == 200
    assert [item["title"] for item in body_response.json()] == ["Campus printers"]


def test_forum_topics_support_category_slug_and_id_filters():
    repo = FakeForumRepository(
        topics=[
            _topic(category_slug="academic-qa", category_id=CATEGORY_ID),
            _topic(
                id=TOPIC_ID_TWO,
                category_id=CATEGORY_ID_TWO,
                category_slug="it-student-services",
                category_name_en="IT / Student Services",
                category_name_vi="CNTT / Dịch vụ sinh viên",
                title="Portal login checklist",
                is_pinned=False,
            ),
        ]
    )

    by_slug = _run(_get("/forum/topics?category=it-student-services", _forum_app(repo)))
    by_id = _run(_get(f"/forum/topics?category_id={CATEGORY_ID_TWO}", _forum_app(repo)))

    assert by_slug.status_code == 200
    assert [item["id"] for item in by_slug.json()] == [str(TOPIC_ID_TWO)]
    assert by_id.status_code == 200
    assert [item["id"] for item in by_id.json()] == [str(TOPIC_ID_TWO)]


def test_forum_topics_sort_pinned_newest_activity_and_most_commented():
    older_pinned = _topic(
        title="Pinned orientation Q&A",
        is_pinned=True,
        last_activity_at=NOW - timedelta(days=7),
        created_at=NOW - timedelta(days=10),
        comments=[],
    )
    active = _topic(
        id=TOPIC_ID_TWO,
        title="Recent active thread",
        is_pinned=False,
        last_activity_at=NOW,
        created_at=NOW,
        comments=[_comment(id=uuid.UUID("dddddddd-dddd-dddd-dddd-ddddddddddde"))],
    )
    busy = _topic(
        id=uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbd"),
        title="Many comments",
        is_pinned=False,
        last_activity_at=NOW - timedelta(hours=2),
        created_at=NOW - timedelta(days=2),
        comment_count=5,
    )
    repo = FakeForumRepository(topics=[active, busy, older_pinned])

    active_response = _run(_get("/forum/topics?sort=newest_activity", _forum_app(repo)))
    commented_response = _run(_get("/forum/topics?sort=most_commented", _forum_app(repo)))

    assert active_response.status_code == 200
    assert active_response.json()[0]["title"] == "Pinned orientation Q&A"
    assert active_response.json()[1]["title"] == "Recent active thread"
    assert commented_response.status_code == 200
    assert commented_response.json()[0]["title"] == "Pinned orientation Q&A"
    assert commented_response.json()[1]["title"] == "Many comments"


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


def test_hidden_comments_show_placeholder_to_students_and_content_to_admins():
    hidden = _comment(deleted=True, content="Moderator-only context")
    repo = FakeForumRepository(comment=hidden)

    student_response = _run(_get(f"/forum/topics/{TOPIC_ID}", _forum_app(repo)))
    admin_response = _run(
        _get(f"/forum/topics/{TOPIC_ID}", _forum_app(repo, user=_admin_user()))
    )

    assert student_response.status_code == 200
    assert student_response.json()["comments"][0]["content"] == "[hidden by moderator]"
    assert student_response.json()["comments"][0]["author_name"] is None
    assert admin_response.status_code == 200
    assert admin_response.json()["comments"][0]["content"] == "Moderator-only context"


def test_archived_topic_is_hidden_from_student_list():
    repo = FakeForumRepository()
    app = _forum_app(repo, user=_admin_user())

    archive_response = _run(_post(f"/forum/topics/{TOPIC_ID}/archive", app))
    topics_response = _run(_get("/forum/topics", _forum_app(repo)))

    assert archive_response.status_code == 200
    assert topics_response.status_code == 200
    assert topics_response.json() == []


def test_archived_topic_detail_and_list_are_visible_to_admins_only():
    archived_topic = _topic(deleted=True, title="Archived moderation topic")
    repo = FakeForumRepository(topics=[archived_topic])

    student_detail = _run(_get(f"/forum/topics/{TOPIC_ID}", _forum_app(repo)))
    admin_detail = _run(_get(f"/forum/topics/{TOPIC_ID}", _forum_app(repo, user=_admin_user())))
    admin_archived = _run(
        _get("/forum/topics?status=archived", _forum_app(repo, user=_admin_user()))
    )

    assert student_detail.status_code == 404
    assert admin_detail.status_code == 200
    assert admin_detail.json()["deleted"] is True
    assert admin_archived.status_code == 200
    assert admin_archived.json()[0]["title"] == "Archived moderation topic"


def test_admin_can_create_notification_from_forum_topic():
    notification_repo = FakeForumNotificationRepository()
    app = _forum_app(
        FakeForumRepository(),
        user=_admin_user(),
        notification_repository=notification_repo,
    )

    response = _run(
        _post(
            f"/forum/topics/{TOPIC_ID}/notification",
            app,
            {"target_scope": "all", "priority": "high"},
        )
    )

    assert response.status_code == 201
    body = response.json()
    assert body["type"] == "forum"
    assert body["status"] == "published"
    assert body["forum_topic_id"] == str(TOPIC_ID)
    assert notification_repo.created[0]["forum_topic_id"] == TOPIC_ID


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
