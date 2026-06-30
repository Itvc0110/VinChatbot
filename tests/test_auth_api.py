from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime

import pytest
from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient

from vinchatbot.app.api import routes_auth
from vinchatbot.app.api.routes_auth import router as auth_router
from vinchatbot.app.core.config import get_settings
from vinchatbot.app.dependencies.auth import get_auth_repository, require_roles
from vinchatbot.app.repositories.auth import AuthenticatedUser, UserAuthRecord
from vinchatbot.app.security.passwords import hash_password, verify_password
from vinchatbot.app.security.sessions import (
    generate_session_token,
    hash_session_token,
    session_expires_at,
)

DEMO_PASSWORD = "Demo@123456"


def _run(awaitable):
    return asyncio.run(asyncio.wait_for(awaitable, timeout=2.0))


class FakeAuthRepository:
    def __init__(self):
        self.student_id = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
        self.admin_id = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
        self.inactive_id = uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
        self.users = {
            "student.business.demo@vinuni.edu.vn": UserAuthRecord(
                id=self.student_id,
                email="student.business.demo@vinuni.edu.vn",
                password_hash=hash_password(DEMO_PASSWORD),
                full_name="Demo Business Student",
                preferred_name="Business Student",
                status="active",
            ),
            "admin.global.demo@vinuni.edu.vn": UserAuthRecord(
                id=self.admin_id,
                email="admin.global.demo@vinuni.edu.vn",
                password_hash=hash_password(DEMO_PASSWORD),
                full_name="Demo Global Admin",
                preferred_name="Global Admin",
                status="active",
            ),
            "inactive.demo@vinuni.edu.vn": UserAuthRecord(
                id=self.inactive_id,
                email="inactive.demo@vinuni.edu.vn",
                password_hash=hash_password(DEMO_PASSWORD),
                full_name="Inactive Demo",
                preferred_name=None,
                status="inactive",
            ),
        }
        self.roles = {
            self.student_id: ("student",),
            self.admin_id: ("global_admin",),
            self.inactive_id: ("student",),
        }
        self.sessions: dict[str, dict] = {}
        self.revoked_sessions: set[uuid.UUID] = set()

    async def find_user_by_email(self, email: str):
        return self.users.get(email.lower())

    async def create_session(self, *, user_id, token_hash, expires_at):
        session_id = uuid.uuid5(uuid.NAMESPACE_URL, f"session:{token_hash}")
        self.sessions[token_hash] = {
            "id": session_id,
            "user_id": user_id,
            "expires_at": expires_at,
            "revoked": False,
        }
        return session_id

    async def get_safe_user_by_id(self, user_id, *, session_id=None):
        user = next((candidate for candidate in self.users.values() if candidate.id == user_id), None)
        if user is None:
            return None
        return self._safe_user(user, session_id=session_id)

    async def get_user_by_session_token_hash(self, token_hash):
        session = self.sessions.get(token_hash)
        if session is None or session["revoked"]:
            return None
        user = next(
            candidate
            for candidate in self.users.values()
            if candidate.id == session["user_id"]
        )
        if user.status != "active":
            return None
        return self._safe_user(user, session_id=session["id"])

    async def revoke_session(self, session_id):
        self.revoked_sessions.add(session_id)
        for session in self.sessions.values():
            if session["id"] == session_id:
                session["revoked"] = True

    def _safe_user(self, user: UserAuthRecord, *, session_id=None) -> AuthenticatedUser:
        student_profile = None
        institute = None
        if user.id == self.student_id:
            student_profile = {
                "id": uuid.UUID("dddddddd-dddd-dddd-dddd-dddddddddddd"),
                "student_id": "D2026VIB001",
                "program": "Bachelor of Business Administration",
                "major": "Finance",
                "cohort": 2026,
                "academic_year": 1,
                "student_status": "active",
                "preferred_language": "vi",
                "advisor_name": "Linh Tran",
                "advisor_email": "advisor.vib.demo@vinuni.edu.vn",
                "ai_personalization_enabled": True,
            }
            institute = {
                "id": uuid.UUID("eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee"),
                "code": "VIB",
                "name_vi": "Viện Kinh doanh Quản trị",
                "name_en": "College of Business and Management",
            }
        return AuthenticatedUser(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            preferred_name=user.preferred_name,
            status=user.status,
            roles=self.roles[user.id],
            session_id=session_id,
            student_profile=student_profile,
            institute=institute,
        )


def _auth_app(repository: FakeAuthRepository) -> FastAPI:
    app = FastAPI()
    app.include_router(auth_router)

    async def fake_repository():
        return repository

    app.dependency_overrides[get_auth_repository] = fake_repository
    return app


async def _login(repository: FakeAuthRepository, *, password: str = DEMO_PASSWORD):
    transport = ASGITransport(app=_auth_app(repository))
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.post(
            "/auth/login",
            json={
                "email": "student.business.demo@vinuni.edu.vn",
                "password": password,
            },
        )


def test_password_verification_accepts_seed_hash_and_rejects_wrong_password():
    password_hash = hash_password(DEMO_PASSWORD)

    assert verify_password(DEMO_PASSWORD, password_hash)
    assert not verify_password("wrong-password", password_hash)
    assert not verify_password(DEMO_PASSWORD, "not-a-valid-hash")


def test_session_token_generation_and_hashing():
    first = generate_session_token()
    second = generate_session_token()

    assert first != second
    assert len(hash_session_token(first)) == 64
    assert hash_session_token(first) == hash_session_token(first)
    assert session_expires_at() > datetime.now(UTC)


def test_login_success_returns_token_and_safe_user_without_password_hash():
    repository = FakeAuthRepository()

    response = _run(_login(repository))

    body = response.json()
    assert response.status_code == 200
    assert body["access_token"]
    assert body["token_type"] == "bearer"
    assert body["user"]["email"] == "student.business.demo@vinuni.edu.vn"
    assert body["user"]["roles"] == ["student"]
    assert body["user"]["student_profile"]["student_id"] == "D2026VIB001"
    assert "password_hash" not in str(body)


def test_login_failure_with_wrong_password_is_generic_401():
    repository = FakeAuthRepository()

    response = _run(_login(repository, password="wrong-password"))

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password."


def test_inactive_user_cannot_login():
    repository = FakeAuthRepository()

    async def request():
        transport = ASGITransport(app=_auth_app(repository))
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.post(
                "/auth/login",
                json={
                    "email": "inactive.demo@vinuni.edu.vn",
                    "password": DEMO_PASSWORD,
                },
            )

    response = _run(request())

    assert response.status_code == 401


def test_login_locks_out_after_repeated_failures(monkeypatch):
    # A2: after LOGIN_MAX_ATTEMPTS failures the endpoint 429s — even with the correct password — until
    # the window rolls off. Reset the module limiter + shrink the threshold for a fast test.
    monkeypatch.setattr(routes_auth, "_login_limiter", None)
    settings = get_settings()
    monkeypatch.setattr(settings, "login_max_attempts", 3)
    monkeypatch.setattr(settings, "login_attempt_window_seconds", 300)
    repository = FakeAuthRepository()

    async def run():
        transport = ASGITransport(app=_auth_app(repository))
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            wrong = [
                (await client.post(
                    "/auth/login",
                    json={"email": "student.business.demo@vinuni.edu.vn", "password": "nope"},
                )).status_code
                for _ in range(3)
            ]
            locked = await client.post(
                "/auth/login",
                json={"email": "student.business.demo@vinuni.edu.vn", "password": "nope"},
            )
            even_correct = await client.post(
                "/auth/login",
                json={"email": "student.business.demo@vinuni.edu.vn", "password": DEMO_PASSWORD},
            )
            return wrong, locked, even_correct

    wrong, locked, even_correct = _run(run())
    assert wrong == [401, 401, 401]
    assert locked.status_code == 429
    assert int(locked.headers.get("Retry-After", "0")) >= 1
    assert even_correct.status_code == 429  # locked regardless of correct password within the window


def test_successful_login_does_not_count_toward_lockout(monkeypatch):
    # Only FAILED attempts count: a correct login clears the counter, so repeated good logins never lock.
    monkeypatch.setattr(routes_auth, "_login_limiter", None)
    settings = get_settings()
    monkeypatch.setattr(settings, "login_max_attempts", 3)
    repository = FakeAuthRepository()

    async def run():
        return [(await _login(repository)).status_code for _ in range(5)]

    assert _run(run()) == [200, 200, 200, 200, 200]


def test_me_returns_safe_current_user_data():
    repository = FakeAuthRepository()

    async def request():
        transport = ASGITransport(app=_auth_app(repository))
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            login = await client.post(
                "/auth/login",
                json={
                    "email": "student.business.demo@vinuni.edu.vn",
                    "password": DEMO_PASSWORD,
                },
            )
            token = login.json()["access_token"]
            return await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})

    response = _run(request())

    body = response.json()
    assert response.status_code == 200
    assert body["email"] == "student.business.demo@vinuni.edu.vn"
    assert body["institute"]["code"] == "VIB"
    assert "password_hash" not in str(body)


def test_logout_revokes_current_session():
    repository = FakeAuthRepository()

    async def request():
        transport = ASGITransport(app=_auth_app(repository))
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            login = await client.post(
                "/auth/login",
                json={
                    "email": "student.business.demo@vinuni.edu.vn",
                    "password": DEMO_PASSWORD,
                },
            )
            token = login.json()["access_token"]
            logout = await client.post(
                "/auth/logout",
                headers={"Authorization": f"Bearer {token}"},
            )
            me = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
            return logout, me

    logout, me = _run(request())

    assert logout.status_code == 200
    assert logout.json() == {"success": True}
    assert me.status_code == 401
    assert repository.revoked_sessions


def test_role_dependency_allows_and_denies():
    allowed_user = AuthenticatedUser(
        id=uuid.uuid4(),
        email="admin.global.demo@vinuni.edu.vn",
        full_name="Demo Global Admin",
        preferred_name=None,
        status="active",
        roles=("global_admin",),
    )
    denied_user = AuthenticatedUser(
        id=uuid.uuid4(),
        email="student.business.demo@vinuni.edu.vn",
        full_name="Demo Student",
        preferred_name=None,
        status="active",
        roles=("student",),
    )
    dependency = require_roles("global_admin")

    assert _run(dependency(allowed_user)) == allowed_user
    with pytest.raises(HTTPException) as error:
        _run(dependency(denied_user))
    assert error.value.status_code == 403
