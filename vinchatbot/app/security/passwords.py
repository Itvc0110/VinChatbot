from __future__ import annotations

import base64
import hashlib
import hmac
import secrets

PASSWORD_HASH_ALGORITHM = "pbkdf2_sha256"
PASSWORD_HASH_ITERATIONS = 210_000
PASSWORD_SALT_BYTES = 16


def hash_password(password: str) -> str:
    """Hash a plaintext password for demo/dev auth storage."""

    salt = secrets.token_bytes(PASSWORD_SALT_BYTES)
    digest = _pbkdf2_digest(password, salt, PASSWORD_HASH_ITERATIONS)
    salt_b64 = base64.urlsafe_b64encode(salt).decode("ascii")
    digest_b64 = base64.urlsafe_b64encode(digest).decode("ascii")
    return f"{PASSWORD_HASH_ALGORITHM}${PASSWORD_HASH_ITERATIONS}${salt_b64}${digest_b64}"


def verify_password(password: str, password_hash: str | None) -> bool:
    """Verify a password against the PBKDF2-SHA256 hashes used by demo seeds."""

    if not password_hash:
        return False

    try:
        algorithm, iterations_raw, salt_b64, expected_b64 = password_hash.split("$", 3)
        iterations = int(iterations_raw)
        salt = base64.urlsafe_b64decode(salt_b64.encode("ascii"))
        expected = base64.urlsafe_b64decode(expected_b64.encode("ascii"))
    except (ValueError, TypeError):
        return False

    if algorithm != PASSWORD_HASH_ALGORITHM or iterations <= 0:
        return False

    actual = _pbkdf2_digest(password, salt, iterations)
    return hmac.compare_digest(actual, expected)


def _pbkdf2_digest(password: str, salt: bytes, iterations: int) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
