from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from vinchatbot.app.db.connection import get_app_db_pool
from vinchatbot.app.dependencies.auth import require_roles
from vinchatbot.app.repositories.auth import AuthenticatedUser
from vinchatbot.app.repositories.personalization import PersonalizationRepository
from vinchatbot.app.schemas.personalization import PersonalizationContext

router = APIRouter(prefix="/personalization", tags=["personalization"])

# Student-only: anonymous callers get 401, admin/staff get 403. Backend-owned context is built
# exclusively from the current student's own data, so non-student roles must never receive it.
StudentUser = Annotated[AuthenticatedUser, Depends(require_roles("student"))]


def get_personalization_repository() -> PersonalizationRepository:
    pool = get_app_db_pool()
    if pool is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="App database is not configured.",
        )
    return PersonalizationRepository(pool)


@router.get("/me/context", response_model=PersonalizationContext)
async def personalization_me_context(
    current_user: StudentUser,
    repository: Annotated[PersonalizationRepository, Depends(get_personalization_repository)],
) -> PersonalizationContext:
    context = await repository.get_context(current_user.id)
    if context is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student profile not found.",
        )
    return context
