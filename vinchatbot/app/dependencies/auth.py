from __future__ import annotations

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status

from vinchatbot.app.db.connection import get_app_db_pool
from vinchatbot.app.repositories.auth import AuthenticatedUser, AuthRepository
from vinchatbot.app.security.sessions import hash_session_token


def invalid_session_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired session.",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_auth_repository() -> AuthRepository:
    pool = get_app_db_pool()
    if pool is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="App database is not configured.",
        )
    return AuthRepository(pool)


def extract_bearer_token(authorization: str | None) -> str:
    if not authorization:
        raise invalid_session_error()

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise invalid_session_error()
    return token.strip()


async def get_bearer_token(
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
) -> str:
    return extract_bearer_token(authorization)


async def get_current_user(
    token: Annotated[str, Depends(get_bearer_token)],
    repository: Annotated[AuthRepository, Depends(get_auth_repository)] = None,
) -> AuthenticatedUser:
    if repository is None:  # pragma: no cover - FastAPI supplies this dependency.
        raise invalid_session_error()
    user = await repository.get_user_by_session_token_hash(hash_session_token(token))
    if user is None:
        raise invalid_session_error()
    return user


async def get_optional_current_user(
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
) -> AuthenticatedUser | None:
    if not authorization:
        return None

    token = extract_bearer_token(authorization)
    repository = get_auth_repository()
    user = await repository.get_user_by_session_token_hash(hash_session_token(token))
    if user is None:
        raise invalid_session_error()
    return user


def require_roles(*roles: str) -> Callable[[AuthenticatedUser], AuthenticatedUser]:
    required = set(roles)

    async def dependency(
        current_user: Annotated[AuthenticatedUser, Depends(get_current_user)] = None,
    ) -> AuthenticatedUser:
        if current_user is None:  # pragma: no cover - FastAPI supplies this dependency.
            raise invalid_session_error()
        if required and not required.intersection(current_user.roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient role.",
            )
        return current_user

    return dependency
