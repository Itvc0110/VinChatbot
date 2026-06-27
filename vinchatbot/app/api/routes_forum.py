from __future__ import annotations

import uuid
from collections.abc import Awaitable
from typing import Annotated, TypeVar

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from psycopg.errors import UndefinedColumn, UndefinedTable

from vinchatbot.app.db.connection import get_app_db_pool
from vinchatbot.app.dependencies.auth import get_current_user, require_roles
from vinchatbot.app.repositories.auth import AuthenticatedUser
from vinchatbot.app.repositories.forum import LOCKED, ForumRepository
from vinchatbot.app.schemas.forum import (
    CreateCommentRequest,
    CreateReportRequest,
    CreateTopicRequest,
    ForumCategoryResponse,
    ForumCommentPatchRequest,
    ForumCommentResponse,
    ForumMemberResponse,
    ForumReportResponse,
    ForumTopicDetail,
    ForumTopicPatchRequest,
    ForumTopicSummary,
    VoteRequest,
    VoteResponse,
)

router = APIRouter(tags=["forum"])
T = TypeVar("T")
MODERATOR_ROLES = {"global_admin", "institute_admin", "staff"}
TOPIC_MODERATION_FIELDS = {"is_pinned", "is_locked", "deleted", "official_comment_id"}
TOPIC_CONTENT_FIELDS = {"title", "content", "category_id", "category_slug", "tags", "attachments"}
COMMENT_MODERATION_FIELDS = {"is_official"}
COMMENT_CONTENT_FIELDS = {"content"}

AuthedUser = Annotated[AuthenticatedUser, Depends(get_current_user)]
ModUser = Annotated[
    AuthenticatedUser,
    Depends(require_roles("global_admin", "institute_admin", "staff")),
]


def get_forum_repository() -> ForumRepository:
    pool = get_app_db_pool()
    if pool is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="App database is not configured.",
        )
    return ForumRepository(pool)


def topic_not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Topic not found.")


def comment_not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found.")


def forum_schema_unavailable() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Forum database schema is not available. Apply forum migrations before using forum features.",
    )


async def run_forum_query(awaitable: Awaitable[T]) -> T:
    try:
        return await awaitable
    except (UndefinedColumn, UndefinedTable) as exc:
        raise forum_schema_unavailable() from exc


def is_moderator(user: AuthenticatedUser) -> bool:
    return bool(MODERATOR_ROLES.intersection(user.roles))


def forbidden() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Insufficient forum permission.",
    )


def unknown_category() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Unknown or inactive category.",
    )


@router.get("/forum/categories", response_model=list[ForumCategoryResponse])
async def list_categories(
    _current_user: AuthedUser,
    repository: Annotated[ForumRepository, Depends(get_forum_repository)],
) -> list[ForumCategoryResponse]:
    categories = await run_forum_query(repository.list_categories())
    return [ForumCategoryResponse(**category) for category in categories]


@router.get("/forum/members", response_model=list[ForumMemberResponse])
async def search_members(
    _current_user: AuthedUser,
    repository: Annotated[ForumRepository, Depends(get_forum_repository)],
    q: Annotated[str, Query(min_length=1, max_length=80)],
) -> list[ForumMemberResponse]:
    members = await run_forum_query(repository.search_members(q))
    return [ForumMemberResponse(**member) for member in members]


@router.get("/forum/topics", response_model=list[ForumTopicSummary])
async def list_topics(
    current_user: AuthedUser,
    repository: Annotated[ForumRepository, Depends(get_forum_repository)],
    category: Annotated[str | None, Query()] = None,
    sort: Annotated[str, Query(pattern="^(new|top|active)$")] = "active",
    q: Annotated[str | None, Query(max_length=120)] = None,
) -> list[ForumTopicSummary]:
    topics = await run_forum_query(
        repository.list_topics(
            user_id=current_user.id,
            category_slug=category,
            sort=sort,
            search=q,
        )
    )
    return [ForumTopicSummary(**topic) for topic in topics]


@router.post(
    "/forum/topics",
    response_model=ForumTopicDetail,
    status_code=status.HTTP_201_CREATED,
)
async def create_topic(
    request: CreateTopicRequest,
    current_user: AuthedUser,
    repository: Annotated[ForumRepository, Depends(get_forum_repository)],
) -> ForumTopicDetail:
    topic = await run_forum_query(
        repository.create_topic(author_user_id=current_user.id, request=request)
    )
    if topic is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unknown or inactive category.",
        )
    return ForumTopicDetail(**topic)


@router.get("/forum/topics/{topic_id}", response_model=ForumTopicDetail)
async def get_topic(
    topic_id: uuid.UUID,
    current_user: AuthedUser,
    repository: Annotated[ForumRepository, Depends(get_forum_repository)],
) -> ForumTopicDetail:
    topic = await run_forum_query(
        repository.get_topic(
            topic_id=topic_id,
            user_id=current_user.id,
            bump_views=True,
        )
    )
    if topic is None:
        raise topic_not_found()
    return ForumTopicDetail(**topic)


@router.get("/forum/topics/{topic_id}/comments", response_model=list[ForumCommentResponse])
async def list_topic_comments(
    topic_id: uuid.UUID,
    current_user: AuthedUser,
    repository: Annotated[ForumRepository, Depends(get_forum_repository)],
) -> list[ForumCommentResponse]:
    comments = await run_forum_query(
        repository.list_comments(topic_id=topic_id, user_id=current_user.id)
    )
    if comments is None:
        raise topic_not_found()
    return [ForumCommentResponse(**comment) for comment in comments]


@router.post("/forum/topics/{topic_id}/comments", response_model=ForumCommentResponse)
async def add_comment(
    topic_id: uuid.UUID,
    request: CreateCommentRequest,
    current_user: AuthedUser,
    repository: Annotated[ForumRepository, Depends(get_forum_repository)],
) -> ForumCommentResponse:
    result = await run_forum_query(
        repository.add_comment(
            topic_id=topic_id,
            author_user_id=current_user.id,
            request=request,
        )
    )
    if result is LOCKED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This topic is locked.",
        )
    if result is None:
        raise topic_not_found()
    return ForumCommentResponse(**result)


@router.post("/forum/topics/{topic_id}/vote", response_model=VoteResponse)
async def vote_topic(
    topic_id: uuid.UUID,
    request: VoteRequest,
    current_user: AuthedUser,
    repository: Annotated[ForumRepository, Depends(get_forum_repository)],
) -> VoteResponse:
    result = await run_forum_query(
        repository.set_vote(
            user_id=current_user.id,
            target_type="topic",
            target_id=topic_id,
            value=request.value,
        )
    )
    if result is None:
        raise topic_not_found()
    return VoteResponse(**result)


@router.post("/forum/comments/{comment_id}/vote", response_model=VoteResponse)
async def vote_comment(
    comment_id: uuid.UUID,
    request: VoteRequest,
    current_user: AuthedUser,
    repository: Annotated[ForumRepository, Depends(get_forum_repository)],
) -> VoteResponse:
    result = await run_forum_query(
        repository.set_vote(
            user_id=current_user.id,
            target_type="comment",
            target_id=comment_id,
            value=request.value,
        )
    )
    if result is None:
        raise comment_not_found()
    return VoteResponse(**result)


@router.post(
    "/forum/reports",
    response_model=ForumReportResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_report(
    request: CreateReportRequest,
    current_user: AuthedUser,
    repository: Annotated[ForumRepository, Depends(get_forum_repository)],
) -> ForumReportResponse:
    report = await run_forum_query(
        repository.create_report(reporter_user_id=current_user.id, request=request)
    )
    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reported content not found.",
        )
    return ForumReportResponse(**report)


@router.patch("/forum/topics/{topic_id}", response_model=ForumTopicDetail)
async def patch_topic(
    topic_id: uuid.UUID,
    request: ForumTopicPatchRequest,
    current_user: AuthedUser,
    repository: Annotated[ForumRepository, Depends(get_forum_repository)],
) -> ForumTopicDetail:
    topic_state = await run_forum_query(repository.get_topic_state(topic_id))
    if topic_state is None:
        raise topic_not_found()

    moderator = is_moderator(current_user)
    if topic_state["deleted"] and not moderator:
        raise topic_not_found()

    changed = request.model_fields_set
    if TOPIC_MODERATION_FIELDS.intersection(changed) and not moderator:
        if changed == {"deleted"} and topic_state["author_user_id"] == current_user.id:
            if request.deleted is not True or topic_state["is_locked"]:
                raise forbidden()
        else:
            raise forbidden()

    if TOPIC_CONTENT_FIELDS.intersection(changed):
        if not moderator and topic_state["author_user_id"] != current_user.id:
            raise forbidden()
        if not moderator and topic_state["is_locked"]:
            raise forbidden()

    topic = await run_forum_query(
        repository.patch_topic(
            topic_id=topic_id,
            request=request,
            actor_user_id=current_user.id,
            include_deleted=moderator or ("deleted" in changed and request.deleted is True),
        )
    )
    if topic is None:
        raise unknown_category()
    return ForumTopicDetail(**topic)


@router.patch("/forum/comments/{comment_id}", response_model=ForumCommentResponse)
async def patch_comment(
    comment_id: uuid.UUID,
    request: ForumCommentPatchRequest,
    current_user: AuthedUser,
    repository: Annotated[ForumRepository, Depends(get_forum_repository)],
) -> ForumCommentResponse:
    comment_state = await run_forum_query(repository.get_comment_state(comment_id))
    if comment_state is None:
        raise comment_not_found()

    moderator = is_moderator(current_user)
    if (comment_state["topic_deleted"] or comment_state["deleted"]) and not moderator:
        raise comment_not_found()

    changed = request.model_fields_set
    if COMMENT_MODERATION_FIELDS.intersection(changed) and not moderator:
        raise forbidden()

    if COMMENT_CONTENT_FIELDS.intersection(changed):
        if not moderator and comment_state["author_user_id"] != current_user.id:
            raise forbidden()
        if not moderator and comment_state["topic_is_locked"]:
            raise forbidden()

    if "deleted" in changed and not moderator:
        if comment_state["author_user_id"] != current_user.id:
            raise forbidden()
        if request.deleted is not True or comment_state["topic_is_locked"]:
            raise forbidden()

    comment = await run_forum_query(
        repository.patch_comment(
            comment_id=comment_id,
            request=request,
            actor_user_id=current_user.id,
        )
    )
    if comment is None:
        raise comment_not_found()
    return ForumCommentResponse(**comment)


@router.delete("/forum/topics/{topic_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_topic(
    topic_id: uuid.UUID,
    current_user: AuthedUser,
    repository: Annotated[ForumRepository, Depends(get_forum_repository)],
) -> Response:
    await patch_topic(
        topic_id,
        ForumTopicPatchRequest(deleted=True),
        current_user,
        repository,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/forum/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_comment(
    comment_id: uuid.UUID,
    current_user: AuthedUser,
    repository: Annotated[ForumRepository, Depends(get_forum_repository)],
) -> Response:
    await patch_comment(
        comment_id,
        ForumCommentPatchRequest(deleted=True),
        current_user,
        repository,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


async def apply_topic_moderation(
    topic_id: uuid.UUID,
    request: ForumTopicPatchRequest,
    current_user: ModUser,
    repository: ForumRepository,
) -> ForumTopicDetail:
    topic = await run_forum_query(
        repository.patch_topic(
            topic_id=topic_id,
            request=request,
            actor_user_id=current_user.id,
            include_deleted=True,
        )
    )
    if topic is None:
        raise topic_not_found()
    return ForumTopicDetail(**topic)


async def apply_comment_moderation(
    comment_id: uuid.UUID,
    request: ForumCommentPatchRequest,
    current_user: ModUser,
    repository: ForumRepository,
) -> ForumCommentResponse:
    comment = await run_forum_query(
        repository.patch_comment(
            comment_id=comment_id,
            request=request,
            actor_user_id=current_user.id,
        )
    )
    if comment is None:
        raise comment_not_found()
    return ForumCommentResponse(**comment)


@router.post("/forum/topics/{topic_id}/pin", response_model=ForumTopicDetail)
async def pin_topic(
    topic_id: uuid.UUID,
    current_user: ModUser,
    repository: Annotated[ForumRepository, Depends(get_forum_repository)],
) -> ForumTopicDetail:
    return await apply_topic_moderation(
        topic_id, ForumTopicPatchRequest(is_pinned=True), current_user, repository
    )


@router.post("/forum/topics/{topic_id}/unpin", response_model=ForumTopicDetail)
async def unpin_topic(
    topic_id: uuid.UUID,
    current_user: ModUser,
    repository: Annotated[ForumRepository, Depends(get_forum_repository)],
) -> ForumTopicDetail:
    return await apply_topic_moderation(
        topic_id, ForumTopicPatchRequest(is_pinned=False), current_user, repository
    )


@router.post("/forum/topics/{topic_id}/lock", response_model=ForumTopicDetail)
async def lock_topic(
    topic_id: uuid.UUID,
    current_user: ModUser,
    repository: Annotated[ForumRepository, Depends(get_forum_repository)],
) -> ForumTopicDetail:
    return await apply_topic_moderation(
        topic_id, ForumTopicPatchRequest(is_locked=True), current_user, repository
    )


@router.post("/forum/topics/{topic_id}/unlock", response_model=ForumTopicDetail)
async def unlock_topic(
    topic_id: uuid.UUID,
    current_user: ModUser,
    repository: Annotated[ForumRepository, Depends(get_forum_repository)],
) -> ForumTopicDetail:
    return await apply_topic_moderation(
        topic_id, ForumTopicPatchRequest(is_locked=False), current_user, repository
    )


@router.post("/forum/topics/{topic_id}/archive", response_model=ForumTopicDetail)
async def archive_topic(
    topic_id: uuid.UUID,
    current_user: ModUser,
    repository: Annotated[ForumRepository, Depends(get_forum_repository)],
) -> ForumTopicDetail:
    return await apply_topic_moderation(
        topic_id, ForumTopicPatchRequest(deleted=True), current_user, repository
    )


@router.post("/forum/comments/{comment_id}/hide", response_model=ForumCommentResponse)
async def hide_comment(
    comment_id: uuid.UUID,
    current_user: ModUser,
    repository: Annotated[ForumRepository, Depends(get_forum_repository)],
) -> ForumCommentResponse:
    return await apply_comment_moderation(
        comment_id, ForumCommentPatchRequest(deleted=True), current_user, repository
    )


@router.post("/forum/comments/{comment_id}/unhide", response_model=ForumCommentResponse)
async def unhide_comment(
    comment_id: uuid.UUID,
    current_user: ModUser,
    repository: Annotated[ForumRepository, Depends(get_forum_repository)],
) -> ForumCommentResponse:
    return await apply_comment_moderation(
        comment_id, ForumCommentPatchRequest(deleted=False), current_user, repository
    )
