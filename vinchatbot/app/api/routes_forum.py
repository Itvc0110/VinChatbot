from __future__ import annotations

import uuid
from collections.abc import Awaitable
from typing import Annotated, TypeVar

from fastapi import APIRouter, Depends, HTTPException, Query, status
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
    ForumCommentResponse,
    ForumMemberResponse,
    ForumReportResponse,
    ForumTopicDetail,
    ForumTopicSummary,
    ModerateCommentRequest,
    ModerateTopicRequest,
    VoteRequest,
    VoteResponse,
)

router = APIRouter(tags=["forum"])
T = TypeVar("T")

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
async def moderate_topic(
    topic_id: uuid.UUID,
    request: ModerateTopicRequest,
    current_user: ModUser,
    repository: Annotated[ForumRepository, Depends(get_forum_repository)],
) -> ForumTopicDetail:
    topic = await run_forum_query(
        repository.moderate_topic(
            topic_id=topic_id,
            request=request,
            mod_user_id=current_user.id,
        )
    )
    if topic is None:
        raise topic_not_found()
    return ForumTopicDetail(**topic)


@router.patch("/forum/comments/{comment_id}", response_model=ForumCommentResponse)
async def moderate_comment(
    comment_id: uuid.UUID,
    request: ModerateCommentRequest,
    current_user: ModUser,
    repository: Annotated[ForumRepository, Depends(get_forum_repository)],
) -> ForumCommentResponse:
    comment = await run_forum_query(
        repository.moderate_comment(
            comment_id=comment_id,
            request=request,
            mod_user_id=current_user.id,
        )
    )
    if comment is None:
        raise comment_not_found()
    return ForumCommentResponse(**comment)
