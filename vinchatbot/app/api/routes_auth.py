from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status

from vinchatbot.app.api.ratelimit import (
    SlidingWindowRateLimiter,
    _client_key,
    _parse_trusted_proxies,
)
from vinchatbot.app.core.config import Settings, get_settings
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


# Per-(email+IP) login brute-force limiter (A2). In-process sliding window — counts only FAILED
# attempts and rejects before verifying once over the limit, so legit logins are never throttled.
_login_limiter: SlidingWindowRateLimiter | None = None


def _get_login_limiter(settings: Settings) -> SlidingWindowRateLimiter:
    global _login_limiter
    if _login_limiter is None:
        _login_limiter = SlidingWindowRateLimiter(
            settings.login_max_attempts, settings.login_attempt_window_seconds
        )
    return _login_limiter


def _login_attempt_key(request: LoginRequest, http_request: Request, settings: Settings) -> str:
    ip = _client_key(http_request, _parse_trusted_proxies(settings.trusted_proxies))
    return f"{(request.email or '').strip().lower()}|{ip}"


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
    http_request: Request,
    repository: Annotated[AuthRepository, Depends(get_auth_repository)],
) -> LoginResponse:
    settings = get_settings()
    limiter = _get_login_limiter(settings)
    key = _login_attempt_key(request, http_request, settings)
    blocked, retry_after = limiter.peek_blocked(key)
    if blocked:
        retry_secs = int(retry_after) + 1
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Please wait and try again.",
            headers={"Retry-After": str(retry_secs)},
        )

    user = await repository.find_user_by_email(request.email)
    if (
        user is None
        or user.status != "active"
        or not verify_password(request.password, user.password_hash)
    ):
        limiter.record(key)  # count only FAILED attempts toward the lockout
        raise invalid_credentials_error()

    limiter.reset_key(key)  # successful login clears the failure count
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
