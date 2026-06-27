from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from vinchatbot.app.db.connection import get_app_db_pool
from vinchatbot.app.dependencies.auth import require_roles
from vinchatbot.app.repositories.admin_notifications import (
    AdminNotificationRepository,
    NotificationPermissionError,
)
from vinchatbot.app.repositories.auth import AuthenticatedUser
from vinchatbot.app.schemas.admin_notifications import (
    AdminNotificationCreateRequest,
    AdminNotificationResponse,
    AdminNotificationScheduleRequest,
    AdminNotificationTargetResponse,
    AdminNotificationUpdateRequest,
)

router = APIRouter(tags=["admin-notifications"])
AdminUser = Annotated[
    AuthenticatedUser,
    Depends(require_roles("global_admin", "institute_admin", "staff")),
]


def get_admin_notification_repository() -> AdminNotificationRepository:
    pool = get_app_db_pool()
    if pool is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="App database is not configured.",
        )
    return AdminNotificationRepository(pool)


def notification_not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Notification not found.",
    )


def notification_forbidden() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Notification target is outside your admin scope.",
    )


@router.get("/admin/notifications", response_model=list[AdminNotificationResponse])
async def list_admin_notifications(
    current_user: AdminUser,
    repository: Annotated[
        AdminNotificationRepository,
        Depends(get_admin_notification_repository),
    ],
) -> list[AdminNotificationResponse]:
    notifications = await repository.list_notifications(current_user)
    return [AdminNotificationResponse(**notification) for notification in notifications]


@router.get("/admin/notifications/targets", response_model=list[AdminNotificationTargetResponse])
async def list_admin_notification_targets(
    current_user: AdminUser,
    repository: Annotated[
        AdminNotificationRepository,
        Depends(get_admin_notification_repository),
    ],
) -> list[AdminNotificationTargetResponse]:
    targets = await repository.list_target_institutes(current_user)
    return [AdminNotificationTargetResponse(**target) for target in targets]


@router.get("/admin/notifications/{notification_id}", response_model=AdminNotificationResponse)
async def get_admin_notification(
    notification_id: uuid.UUID,
    current_user: AdminUser,
    repository: Annotated[
        AdminNotificationRepository,
        Depends(get_admin_notification_repository),
    ],
) -> AdminNotificationResponse:
    notification = await repository.get_notification(
        notification_id=notification_id,
        current_user=current_user,
    )
    if notification is None:
        raise notification_not_found()
    return AdminNotificationResponse(**notification)


@router.post(
    "/admin/notifications",
    response_model=AdminNotificationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_admin_notification(
    request: AdminNotificationCreateRequest,
    current_user: AdminUser,
    repository: Annotated[
        AdminNotificationRepository,
        Depends(get_admin_notification_repository),
    ],
) -> AdminNotificationResponse:
    try:
        notification = await repository.create_notification(
            current_user=current_user,
            request=request,
        )
    except NotificationPermissionError as exc:
        raise notification_forbidden() from exc
    return AdminNotificationResponse(**notification)


@router.patch("/admin/notifications/{notification_id}", response_model=AdminNotificationResponse)
async def update_admin_notification(
    notification_id: uuid.UUID,
    request: AdminNotificationUpdateRequest,
    current_user: AdminUser,
    repository: Annotated[
        AdminNotificationRepository,
        Depends(get_admin_notification_repository),
    ],
) -> AdminNotificationResponse:
    try:
        notification = await repository.update_notification(
            notification_id=notification_id,
            current_user=current_user,
            request=request,
        )
    except NotificationPermissionError as exc:
        raise notification_forbidden() from exc
    if notification is None:
        raise notification_not_found()
    return AdminNotificationResponse(**notification)


@router.post(
    "/admin/notifications/{notification_id}/publish",
    response_model=AdminNotificationResponse,
)
async def publish_admin_notification(
    notification_id: uuid.UUID,
    current_user: AdminUser,
    repository: Annotated[
        AdminNotificationRepository,
        Depends(get_admin_notification_repository),
    ],
) -> AdminNotificationResponse:
    notification = await repository.publish_notification(
        notification_id=notification_id,
        current_user=current_user,
    )
    if notification is None:
        raise notification_not_found()
    return AdminNotificationResponse(**notification)


@router.post(
    "/admin/notifications/{notification_id}/schedule",
    response_model=AdminNotificationResponse,
)
async def schedule_admin_notification(
    notification_id: uuid.UUID,
    request: AdminNotificationScheduleRequest,
    current_user: AdminUser,
    repository: Annotated[
        AdminNotificationRepository,
        Depends(get_admin_notification_repository),
    ],
) -> AdminNotificationResponse:
    notification = await repository.schedule_notification(
        notification_id=notification_id,
        current_user=current_user,
        request=request,
    )
    if notification is None:
        raise notification_not_found()
    return AdminNotificationResponse(**notification)


@router.post(
    "/admin/notifications/{notification_id}/archive",
    response_model=AdminNotificationResponse,
)
async def archive_admin_notification(
    notification_id: uuid.UUID,
    current_user: AdminUser,
    repository: Annotated[
        AdminNotificationRepository,
        Depends(get_admin_notification_repository),
    ],
) -> AdminNotificationResponse:
    notification = await repository.archive_notification(
        notification_id=notification_id,
        current_user=current_user,
    )
    if notification is None:
        raise notification_not_found()
    return AdminNotificationResponse(**notification)
