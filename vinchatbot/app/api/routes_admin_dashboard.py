from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from vinchatbot.app.db.connection import get_app_db_pool
from vinchatbot.app.dependencies.auth import require_roles
from vinchatbot.app.repositories.admin_dashboard import AdminDashboardRepository
from vinchatbot.app.repositories.auth import AuthenticatedUser
from vinchatbot.app.schemas.admin_dashboard import AdminDashboardResponse

router = APIRouter(prefix="/admin", tags=["admin"])
AdminUser = Annotated[
    AuthenticatedUser,
    Depends(require_roles("global_admin", "institute_admin", "staff")),
]


def get_admin_dashboard_repository() -> AdminDashboardRepository:
    pool = get_app_db_pool()
    if pool is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="App database is not configured.",
        )
    return AdminDashboardRepository(pool)


@router.get("/dashboard", response_model=AdminDashboardResponse)
async def admin_dashboard(
    current_user: AdminUser,
    repository: Annotated[
        AdminDashboardRepository,
        Depends(get_admin_dashboard_repository),
    ],
) -> AdminDashboardResponse:
    dashboard = await repository.get_dashboard(current_user)
    return AdminDashboardResponse(**dashboard)
