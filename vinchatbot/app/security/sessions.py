from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta

DEFAULT_SESSION_DAYS = 7


def generate_session_token() -> str:
    """Generate an opaque bearer token. The token itself is never stored."""

    return secrets.token_urlsafe(32)


def hash_session_token(token: str) -> str:
    """Hash an opaque token before database storage or lookup."""

    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def session_expires_at(days: int = DEFAULT_SESSION_DAYS) -> datetime:
    return datetime.now(UTC) + timedelta(days=days)
