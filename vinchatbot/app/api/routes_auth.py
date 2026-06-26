from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from vinchatbot.app.dependencies.auth import get_auth_repository, get_current_user
from vinchatbot.app.repositories.auth import AuthenticatedUser, AuthRepository
from vinchatbot.app.schemas.auth import (
    CurrentUserResponse,
    LoginRequest,
    LoginResponse,
    LogoutResponse,
)
from vinchatbot.app.security.passwords import verify_password
from vinchatbot.app.security.sessions import (
    generate_session_token,
    hash_session_token,
    session_expires_at,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def invalid_credentials_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid email or password.",
        headers={"WWW-Authenticate": "Bearer"},
    )


def current_user_response(user: AuthenticatedUser) -> CurrentUserResponse:
    return CurrentUserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        preferred_name=user.preferred_name,
        roles=list(user.roles),
        student_profile=user.student_profile,
        institute=user.institute,
    )


@router.post("/login", response_model=LoginResponse)
async def login(
    request: LoginRequest,
    repository: Annotated[AuthRepository, Depends(get_auth_repository)],
) -> LoginResponse:
    user = await repository.find_user_by_email(request.email)
    if (
        user is None
        or user.status != "active"
        or not verify_password(request.password, user.password_hash)
    ):
        raise invalid_credentials_error()

    token = generate_session_token()
    session_id = await repository.create_session(
        user_id=user.id,
        token_hash=hash_session_token(token),
        expires_at=session_expires_at(),
    )
    safe_user = await repository.get_safe_user_by_id(user.id, session_id=session_id)
    if safe_user is None:  # pragma: no cover - user existed before session creation.
        raise invalid_credentials_error()

    return LoginResponse(access_token=token, user=current_user_response(safe_user))


@router.get("/me", response_model=CurrentUserResponse)
async def me(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> CurrentUserResponse:
    return current_user_response(current_user)


@router.post("/logout", response_model=LogoutResponse)
async def logout(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    repository: Annotated[AuthRepository, Depends(get_auth_repository)],
) -> LogoutResponse:
    if current_user.session_id is not None:
        await repository.revoke_session(current_user.session_id)
    return LogoutResponse(success=True)
