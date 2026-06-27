from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from vinchatbot.app.db.connection import get_app_db_pool
from vinchatbot.app.dependencies.auth import get_current_user
from vinchatbot.app.repositories.auth import AuthenticatedUser
from vinchatbot.app.repositories.conversations import ConversationRepository
from vinchatbot.app.schemas.conversations import (
    ConversationDeleteResponse,
    ConversationDetailResponse,
    ConversationSummaryResponse,
    CreateConversationRequest,
    MessageResponse,
    UpdateConversationRequest,
)

router = APIRouter(tags=["conversations"])


def get_conversation_repository() -> ConversationRepository:
    pool = get_app_db_pool()
    if pool is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="App database is not configured.",
        )
    return ConversationRepository(pool)


def conversation_not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Conversation not found.",
    )


@router.get("/conversations", response_model=list[ConversationSummaryResponse])
async def list_conversations(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    repository: Annotated[ConversationRepository, Depends(get_conversation_repository)],
) -> list[ConversationSummaryResponse]:
    conversations = await repository.list_conversations(current_user.id)
    return [ConversationSummaryResponse(**conversation) for conversation in conversations]


@router.post(
    "/conversations",
    response_model=ConversationDetailResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_conversation(
    request: CreateConversationRequest,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    repository: Annotated[ConversationRepository, Depends(get_conversation_repository)],
) -> ConversationDetailResponse:
    conversation = await repository.create_conversation(user_id=current_user.id, request=request)
    return ConversationDetailResponse(**conversation)


@router.get("/conversations/{conversation_id}", response_model=ConversationDetailResponse)
async def get_conversation(
    conversation_id: uuid.UUID,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    repository: Annotated[ConversationRepository, Depends(get_conversation_repository)],
) -> ConversationDetailResponse:
    conversation = await repository.get_conversation(
        user_id=current_user.id,
        conversation_id=conversation_id,
    )
    if conversation is None:
        raise conversation_not_found()
    return ConversationDetailResponse(**conversation)


@router.get("/conversations/{conversation_id}/messages", response_model=list[MessageResponse])
async def list_messages(
    conversation_id: uuid.UUID,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    repository: Annotated[ConversationRepository, Depends(get_conversation_repository)],
) -> list[MessageResponse]:
    messages = await repository.list_messages(
        user_id=current_user.id,
        conversation_id=conversation_id,
    )
    if messages is None:
        raise conversation_not_found()
    return [MessageResponse(**message) for message in messages]


@router.patch("/conversations/{conversation_id}", response_model=ConversationDetailResponse)
async def update_conversation(
    conversation_id: uuid.UUID,
    request: UpdateConversationRequest,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    repository: Annotated[ConversationRepository, Depends(get_conversation_repository)],
) -> ConversationDetailResponse:
    conversation = await repository.update_conversation(
        user_id=current_user.id,
        conversation_id=conversation_id,
        request=request,
    )
    if conversation is None:
        raise conversation_not_found()
    return ConversationDetailResponse(**conversation)


@router.delete("/conversations/{conversation_id}", response_model=ConversationDeleteResponse)
async def delete_conversation(
    conversation_id: uuid.UUID,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    repository: Annotated[ConversationRepository, Depends(get_conversation_repository)],
) -> ConversationDeleteResponse:
    deleted = await repository.delete_conversation(
        user_id=current_user.id,
        conversation_id=conversation_id,
    )
    if not deleted:
        raise conversation_not_found()
    return ConversationDeleteResponse(deleted=True)
