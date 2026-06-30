from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import ValidationError

from vinchatbot.app.agents.ticket_suggest import suggest_ticket_draft
from vinchatbot.app.db.connection import get_app_db_pool
from vinchatbot.app.dependencies.auth import require_roles
from vinchatbot.app.repositories.auth import AuthenticatedUser
from vinchatbot.app.repositories.tickets import TicketRepository
from vinchatbot.app.schemas.tickets import (
    AddTicketMessageRequest,
    AdminTicketFilters,
    AdminUpdateTicketRequest,
    CreateTicketRequest,
    SuggestedTicketDraft,
    SuggestTicketRequest,
    TicketDetailResponse,
    TicketMessageResponse,
    TicketSummaryResponse,
)

router = APIRouter(tags=["tickets"])
StudentUser = Annotated[AuthenticatedUser, Depends(require_roles("student"))]
AdminUser = Annotated[
    AuthenticatedUser,
    Depends(require_roles("global_admin", "institute_admin", "staff")),
]


def get_ticket_repository() -> TicketRepository:
    pool = get_app_db_pool()
    if pool is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="App database is not configured.",
        )
    return TicketRepository(pool)


def ticket_not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Ticket not found.",
    )


@router.get("/tickets/me", response_model=list[TicketSummaryResponse])
async def list_my_tickets(
    current_user: StudentUser,
    repository: Annotated[TicketRepository, Depends(get_ticket_repository)],
) -> list[TicketSummaryResponse]:
    tickets = await repository.list_student_tickets(current_user.id)
    return [TicketSummaryResponse(**ticket) for ticket in tickets]


@router.get("/tickets/{ticket_id}", response_model=TicketDetailResponse)
async def get_my_ticket(
    ticket_id: uuid.UUID,
    current_user: StudentUser,
    repository: Annotated[TicketRepository, Depends(get_ticket_repository)],
) -> TicketDetailResponse:
    ticket = await repository.get_student_ticket(ticket_id=ticket_id, user_id=current_user.id)
    if ticket is None:
        raise ticket_not_found()
    return TicketDetailResponse(**ticket)


@router.post("/tickets/suggest", response_model=SuggestedTicketDraft)
async def suggest_ticket(
    request: SuggestTicketRequest,
    current_user: StudentUser,
) -> SuggestedTicketDraft:
    """Vinnie drafts a ticket (summary/description/category) from the conversation for the student to
    review before sending. Advisory only — nothing is persisted here. Fails open to a heuristic draft."""
    return await suggest_ticket_draft(request)


@router.post("/tickets", response_model=TicketDetailResponse, status_code=status.HTTP_201_CREATED)
async def create_ticket(
    request: CreateTicketRequest,
    current_user: StudentUser,
    repository: Annotated[TicketRepository, Depends(get_ticket_repository)],
) -> TicketDetailResponse:
    ticket = await repository.create_student_ticket(user_id=current_user.id, request=request)
    if ticket is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student profile not found.",
        )
    return TicketDetailResponse(**ticket)


@router.post("/tickets/{ticket_id}/messages", response_model=TicketMessageResponse)
async def add_student_ticket_message(
    ticket_id: uuid.UUID,
    request: AddTicketMessageRequest,
    current_user: StudentUser,
    repository: Annotated[TicketRepository, Depends(get_ticket_repository)],
) -> TicketMessageResponse:
    message = await repository.add_student_message(
        ticket_id=ticket_id,
        user_id=current_user.id,
        request=request,
    )
    if message is None:
        raise ticket_not_found()
    return TicketMessageResponse(**message)


@router.get("/admin/tickets", response_model=list[TicketSummaryResponse])
async def list_admin_tickets(
    current_user: AdminUser,
    repository: Annotated[TicketRepository, Depends(get_ticket_repository)],
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    priority: Annotated[str | None, Query()] = None,
    include_archived: Annotated[bool, Query()] = False,
) -> list[TicketSummaryResponse]:
    filters = _admin_filters(
        status_value=status_filter,
        priority=priority,
        include_archived=include_archived,
    )
    tickets = await repository.list_admin_tickets(current_user=current_user, filters=filters)
    return [TicketSummaryResponse(**ticket) for ticket in tickets]


@router.get("/admin/tickets/{ticket_id}", response_model=TicketDetailResponse)
async def get_admin_ticket(
    ticket_id: uuid.UUID,
    current_user: AdminUser,
    repository: Annotated[TicketRepository, Depends(get_ticket_repository)],
) -> TicketDetailResponse:
    ticket = await repository.get_admin_ticket(ticket_id=ticket_id, current_user=current_user)
    if ticket is None:
        raise ticket_not_found()
    return TicketDetailResponse(**ticket)


@router.patch("/admin/tickets/{ticket_id}", response_model=TicketDetailResponse)
async def update_admin_ticket(
    ticket_id: uuid.UUID,
    request: AdminUpdateTicketRequest,
    current_user: AdminUser,
    repository: Annotated[TicketRepository, Depends(get_ticket_repository)],
) -> TicketDetailResponse:
    ticket = await repository.update_admin_ticket(
        ticket_id=ticket_id,
        current_user=current_user,
        request=request,
    )
    if ticket is None:
        raise ticket_not_found()
    return TicketDetailResponse(**ticket)


@router.post("/admin/tickets/{ticket_id}/messages", response_model=TicketMessageResponse)
async def add_admin_ticket_message(
    ticket_id: uuid.UUID,
    request: AddTicketMessageRequest,
    current_user: AdminUser,
    repository: Annotated[TicketRepository, Depends(get_ticket_repository)],
) -> TicketMessageResponse:
    message = await repository.add_admin_message(
        ticket_id=ticket_id,
        current_user=current_user,
        request=request,
    )
    if message is None:
        raise ticket_not_found()
    return TicketMessageResponse(**message)


def _admin_filters(
    *,
    status_value: str | None,
    priority: str | None,
    include_archived: bool,
) -> AdminTicketFilters:
    try:
        return AdminTicketFilters(
            status=status_value,
            priority=priority,
            include_archived=include_archived,
        )
    except ValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail=[
                {
                    "loc": error["loc"],
                    "msg": error["msg"],
                    "type": error["type"],
                }
                for error in exc.errors()
            ],
        ) from exc
