from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from psycopg_pool import AsyncConnectionPool


@dataclass(frozen=True)
class UserAuthRecord:
    id: uuid.UUID
    email: str
    password_hash: str | None
    full_name: str
    preferred_name: str | None
    status: str


@dataclass(frozen=True)
class AuthenticatedUser:
    id: uuid.UUID
    email: str
    full_name: str
    preferred_name: str | None
    status: str
    roles: tuple[str, ...]
    session_id: uuid.UUID | None = None
    student_profile: dict[str, Any] | None = None
    institute: dict[str, Any] | None = None


class AuthRepository:
    """Repository for session-based app auth.

    Password hashes are only exposed through `find_user_by_email()` for immediate
    verification by the auth route. Safe user methods never return password_hash.
    """

    def __init__(self, pool: AsyncConnectionPool):
        self.pool = pool

    async def find_user_by_email(self, email: str) -> UserAuthRecord | None:
        row = await self._fetchone(
            """
            select id, email, password_hash, full_name, preferred_name, status
            from users
            where lower(email) = lower(%s)
            """,
            (email,),
        )
        if row is None:
            return None
        return UserAuthRecord(
            id=row["id"],
            email=row["email"],
            password_hash=row["password_hash"],
            full_name=row["full_name"],
            preferred_name=row["preferred_name"],
            status=row["status"],
        )

    async def fetch_user_roles(self, user_id: uuid.UUID) -> tuple[str, ...]:
        rows = await self._fetchall(
            """
            select r.code
            from user_roles ur
            join roles r on r.id = ur.role_id
            where ur.user_id = %s
            order by r.code
            """,
            (user_id,),
        )
        return tuple(str(row["code"]) for row in rows)

    async def create_session(
        self,
        *,
        user_id: uuid.UUID,
        token_hash: str,
        expires_at: datetime,
    ) -> uuid.UUID:
        row = await self._fetchone(
            """
            insert into sessions (user_id, token_hash, expires_at)
            values (%s, %s, %s)
            returning id
            """,
            (user_id, token_hash, expires_at),
        )
        if row is None:  # pragma: no cover - returning id should always produce one row.
            raise RuntimeError("Session creation returned no id.")
        return row["id"]

    async def get_safe_user_by_id(
        self,
        user_id: uuid.UUID,
        *,
        session_id: uuid.UUID | None = None,
    ) -> AuthenticatedUser | None:
        row = await self._fetchone(
            """
            select id, email, full_name, preferred_name, status
            from users
            where id = %s
            """,
            (user_id,),
        )
        if row is None:
            return None
        return await self._build_authenticated_user(row, session_id=session_id)

    async def get_user_by_session_token_hash(
        self,
        token_hash: str,
    ) -> AuthenticatedUser | None:
        row = await self._fetchone(
            """
            select
                s.id as session_id,
                u.id,
                u.email,
                u.full_name,
                u.preferred_name,
                u.status
            from sessions s
            join users u on u.id = s.user_id
            where s.token_hash = %s
              and s.revoked_at is null
              and s.expires_at > now()
            """,
            (token_hash,),
        )
        if row is None or row["status"] != "active":
            return None
        return await self._build_authenticated_user(row, session_id=row["session_id"])

    async def revoke_session(self, session_id: uuid.UUID) -> None:
        await self._execute(
            """
            update sessions
            set revoked_at = now()
            where id = %s and revoked_at is null
            """,
            (session_id,),
        )

    async def _build_authenticated_user(
        self,
        row: dict[str, Any],
        *,
        session_id: uuid.UUID | None,
    ) -> AuthenticatedUser:
        roles = await self.fetch_user_roles(row["id"])
        profile, institute = await self._fetch_student_context(row["id"])
        return AuthenticatedUser(
            id=row["id"],
            email=row["email"],
            full_name=row["full_name"],
            preferred_name=row["preferred_name"],
            status=row["status"],
            roles=roles,
            session_id=session_id,
            student_profile=profile,
            institute=institute,
        )

    async def _fetch_student_context(
        self,
        user_id: uuid.UUID,
    ) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
        row = await self._fetchone(
            """
            select
                sp.id,
                sp.student_id,
                sp.program,
                sp.major,
                sp.cohort,
                sp.academic_year,
                sp.student_status,
                sp.preferred_language,
                sp.advisor_name,
                sp.advisor_email,
                sp.ai_personalization_enabled,
                i.id as institute_id,
                i.code as institute_code,
                i.name_vi as institute_name_vi,
                i.name_en as institute_name_en
            from student_profiles sp
            join institutes i on i.id = sp.institute_id
            where sp.user_id = %s
            """,
            (user_id,),
        )
        if row is None:
            return None, None

        institute = {
            "id": row["institute_id"],
            "code": row["institute_code"],
            "name_vi": row["institute_name_vi"],
            "name_en": row["institute_name_en"],
        }
        profile = {
            "id": row["id"],
            "student_id": row["student_id"],
            "program": row["program"],
            "major": row["major"],
            "cohort": row["cohort"],
            "academic_year": row["academic_year"],
            "student_status": row["student_status"],
            "preferred_language": row["preferred_language"],
            "advisor_name": row["advisor_name"],
            "advisor_email": row["advisor_email"],
            "ai_personalization_enabled": row["ai_personalization_enabled"],
        }
        return profile, institute

    async def _fetchone(self, query: str, params: tuple[Any, ...]) -> dict[str, Any] | None:
        async with self.pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, params)
                return await cur.fetchone()

    async def _fetchall(self, query: str, params: tuple[Any, ...]) -> list[dict[str, Any]]:
        async with self.pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, params)
                rows = await cur.fetchall()
        return list(rows)

    async def _execute(self, query: str, params: tuple[Any, ...]) -> None:
        async with self.pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, params)
