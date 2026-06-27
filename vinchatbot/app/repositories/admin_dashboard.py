from __future__ import annotations

import uuid
from typing import Any

from psycopg_pool import AsyncConnectionPool

from vinchatbot.app.repositories.auth import AuthenticatedUser

ADMIN_INSTITUTE_CODE_BY_EMAIL_PREFIX = {
    "admin.business": "VIB",
    "admin.cecs": "CECS",
    "admin.health": "CHS",
    "admin.liberal": "CASE",
}
ADMIN_ROLES = {"global_admin", "institute_admin", "staff"}
OPEN_TICKET_STATUSES = (
    "submitted",
    "open",
    "in_progress",
    "waiting_on_student",
)
NEED_ADMIN_RESPONSE_STATUSES = ("submitted", "open", "in_progress")
TICKET_STATUSES = (
    "submitted",
    "open",
    "in_progress",
    "waiting_on_student",
    "resolved",
    "closed",
)
TICKET_PRIORITIES = ("low", "medium", "high", "urgent")


class AdminDashboardRepository:
    """Read-only aggregate repository for the admin dashboard."""

    def __init__(self, pool: AsyncConnectionPool):
        self.pool = pool

    async def get_dashboard(self, current_user: AuthenticatedUser) -> dict[str, Any]:
        scope = await self._admin_institute_scope(current_user)
        if scope is _NO_ADMIN_SCOPE:
            return self._empty_dashboard(kind="none")

        return {
            "scope": await self._scope_response(scope),
            "overview": await self._overview(scope),
            "ticket_counts_by_status": await self._ticket_counts(
                scope=scope,
                field="status",
                keys=TICKET_STATUSES,
            ),
            "ticket_counts_by_priority": await self._ticket_counts(
                scope=scope,
                field="priority",
                keys=TICKET_PRIORITIES,
            ),
            "student_counts_by_institute": await self._student_counts_by_institute(scope),
            "recent_tickets": await self._recent_tickets(scope),
            "upcoming_items": await self._upcoming_items(scope),
        }

    async def _overview(self, scope: uuid.UUID | None) -> dict[str, int]:
        return {
            "total_users": await self._count_users(scope),
            "total_students": await self._count_student_profiles(scope),
            "total_institutes": await self._count_institutes(scope),
            "total_tickets": await self._count_tickets(scope),
            "open_tickets": await self._count_tickets(scope, statuses=OPEN_TICKET_STATUSES),
            "need_admin_response": await self._count_tickets(
                scope,
                statuses=NEED_ADMIN_RESPONSE_STATUSES,
            ),
            "urgent_tickets": await self._count_tickets(scope, priorities=("urgent",)),
            "upcoming_deadlines": await self._count_deadlines(scope),
            "upcoming_schedules": await self._count_schedules(scope),
            "upcoming_events": await self._count_events(scope),
            "published_notifications": await self._count_notifications(scope),
        }

    async def _scope_response(self, scope: uuid.UUID | None) -> dict[str, Any]:
        if scope is None:
            return {"kind": "global", "institute_id": None, "institute_code": None}
        row = await self._fetchone(
            "select id, code from institutes where id = %s",
            (scope,),
        )
        return {
            "kind": "institute",
            "institute_id": scope,
            "institute_code": row["code"] if row else None,
        }

    async def _count_users(self, scope: uuid.UUID | None) -> int:
        if scope is None:
            return await self._count("select count(*) as count from users", ())
        return await self._count(
            """
            select count(distinct u.id) as count
            from users u
            join student_profiles sp on sp.user_id = u.id
            where sp.institute_id = %s
            """,
            (scope,),
        )

    async def _count_student_profiles(self, scope: uuid.UUID | None) -> int:
        clause, params = self._student_scope_clause(scope, "sp")
        return await self._count(
            f"select count(*) as count from student_profiles sp {clause}",
            tuple(params),
        )

    async def _count_institutes(self, scope: uuid.UUID | None) -> int:
        if scope is None:
            return await self._count("select count(*) as count from institutes", ())
        return await self._count(
            "select count(*) as count from institutes where id = %s",
            (scope,),
        )

    async def _count_tickets(
        self,
        scope: uuid.UUID | None,
        *,
        statuses: tuple[str, ...] = (),
        priorities: tuple[str, ...] = (),
    ) -> int:
        clauses = ["t.deleted = false"]
        params: list[Any] = []
        if scope is not None:
            clauses.append("t.institute_id = %s")
            params.append(scope)
        if statuses:
            clauses.append("t.status = any(%s)")
            params.append(list(statuses))
        if priorities:
            clauses.append("t.priority = any(%s)")
            params.append(list(priorities))

        return await self._count(
            f"""
            select count(*) as count
            from tickets t
            where {" and ".join(clauses)}
            """,
            tuple(params),
        )

    async def _count_deadlines(self, scope: uuid.UUID | None) -> int:
        scope_clause, params = self._student_scope_clause(scope, "sp")
        extra = "and d.due_at >= now()" if scope_clause else "where d.due_at >= now()"
        return await self._count(
            f"""
            select count(*) as count
            from deadlines d
            left join student_profiles sp on sp.id = d.student_profile_id
            {scope_clause}
            {extra}
            """,
            tuple(params),
        )

    async def _count_schedules(self, scope: uuid.UUID | None) -> int:
        scope_clause, params = self._student_scope_clause(scope, "sp")
        extra = "and s.end_time >= now()" if scope_clause else "where s.end_time >= now()"
        return await self._count(
            f"""
            select count(*) as count
            from schedules s
            join student_profiles sp on sp.id = s.student_profile_id
            {scope_clause}
            {extra}
            """,
            tuple(params),
        )

    async def _count_events(self, scope: uuid.UUID | None) -> int:
        scope_clause, params = self._audience_scope_clause(scope, "e")
        extra = (
            "and coalesce(e.end_time, e.start_time) >= now()"
            if scope_clause
            else "where coalesce(e.end_time, e.start_time) >= now()"
        )
        return await self._count(
            f"""
            select count(*) as count
            from events e
            {scope_clause}
            {extra}
            """,
            tuple(params),
        )

    async def _count_notifications(self, scope: uuid.UUID | None) -> int:
        scope_clause, params = self._audience_scope_clause(scope, "n")
        extra = "and n.status = 'published'" if scope_clause else "where n.status = 'published'"
        return await self._count(
            f"""
            select count(*) as count
            from notifications n
            {scope_clause}
            {extra}
            """,
            tuple(params),
        )

    async def _ticket_counts(
        self,
        *,
        scope: uuid.UUID | None,
        field: str,
        keys: tuple[str, ...],
    ) -> list[dict[str, Any]]:
        if field not in {"status", "priority"}:  # pragma: no cover - internal guard.
            raise ValueError("Unsupported ticket count field.")

        scope_clause = ""
        params: list[Any] = []
        if scope is not None:
            scope_clause = "and t.institute_id = %s"
            params.append(scope)

        rows = await self._fetchall(
            f"""
            select t.{field} as key, count(*)::int as count
            from tickets t
            where t.deleted = false
            {scope_clause}
            group by t.{field}
            """,
            tuple(params),
        )
        counts = {str(row["key"]): int(row["count"]) for row in rows}
        return [{"key": key, "count": counts.get(key, 0)} for key in keys]

    async def _student_counts_by_institute(
        self,
        scope: uuid.UUID | None,
    ) -> list[dict[str, Any]]:
        clause = ""
        params: list[Any] = []
        if scope is not None:
            clause = "where i.id = %s"
            params.append(scope)

        rows = await self._fetchall(
            f"""
            select
                i.id as institute_id,
                i.code as institute_code,
                i.name_en as institute_name_en,
                i.name_vi as institute_name_vi,
                count(sp.id)::int as student_count
            from institutes i
            left join student_profiles sp on sp.institute_id = i.id
            {clause}
            group by i.id, i.code, i.name_en, i.name_vi
            order by i.code
            """,
            tuple(params),
        )
        return [dict(row) for row in rows]

    async def _recent_tickets(self, scope: uuid.UUID | None) -> list[dict[str, Any]]:
        scope_clause = ""
        params: list[Any] = []
        if scope is not None:
            scope_clause = "and t.institute_id = %s"
            params.append(scope)

        rows = await self._fetchall(
            f"""
            select
                t.id,
                t.subject,
                t.status,
                t.priority,
                sp.student_id,
                u.full_name as student_name,
                t.institute_id,
                i.code as institute_code,
                t.due_at,
                t.created_at,
                t.updated_at
            from tickets t
            join student_profiles sp on sp.id = t.student_profile_id
            join users u on u.id = sp.user_id
            left join institutes i on i.id = t.institute_id
            where t.deleted = false
            {scope_clause}
            order by t.updated_at desc, t.created_at desc
            limit 6
            """,
            tuple(params),
        )
        return [dict(row) for row in rows]

    async def _upcoming_items(self, scope: uuid.UUID | None) -> list[dict[str, Any]]:
        deadline_scope, deadline_params = self._student_scope_clause(scope, "dsp")
        schedule_scope, schedule_params = self._student_scope_clause(scope, "ssp")
        event_scope, event_params = self._audience_scope_clause(scope, "e")
        notification_scope, notification_params = self._audience_scope_clause(scope, "n")
        params = [
            *deadline_params,
            *schedule_params,
            *event_params,
            *notification_params,
        ]

        deadline_filter = (
            "and d.due_at >= now()" if deadline_scope else "where d.due_at >= now()"
        )
        schedule_filter = (
            "and s.end_time >= now()" if schedule_scope else "where s.end_time >= now()"
        )
        event_filter = (
            "and coalesce(e.end_time, e.start_time) >= now()"
            if event_scope
            else "where coalesce(e.end_time, e.start_time) >= now()"
        )
        notification_filter = (
            "and n.status in ('published', 'draft')"
            if notification_scope
            else "where n.status in ('published', 'draft')"
        )
        notification_time_filter = (
            "and coalesce(n.deadline, n.event_date, n.start_date, n.created_at) >= now()"
        )

        rows = await self._fetchall(
            f"""
            with upcoming as (
                select
                    d.id,
                    'deadline'::text as item_type,
                    d.title,
                    d.due_at as starts_at,
                    null::timestamptz as ends_at,
                    c.course_code,
                    dsp.institute_id,
                    i.code as institute_code,
                    d.source_title,
                    d.source_url
                from deadlines d
                left join student_profiles dsp on dsp.id = d.student_profile_id
                left join courses c on c.id = d.course_id
                left join institutes i on i.id = dsp.institute_id
                {deadline_scope}
                {deadline_filter}
                union all
                select
                    s.id,
                    'schedule'::text as item_type,
                    s.title,
                    s.start_time as starts_at,
                    s.end_time as ends_at,
                    c.course_code,
                    ssp.institute_id,
                    i.code as institute_code,
                    null::text as source_title,
                    null::text as source_url
                from schedules s
                join student_profiles ssp on ssp.id = s.student_profile_id
                left join courses c on c.id = s.course_id
                left join institutes i on i.id = ssp.institute_id
                {schedule_scope}
                {schedule_filter}
                union all
                select
                    e.id,
                    'event'::text as item_type,
                    e.title,
                    e.start_time as starts_at,
                    e.end_time as ends_at,
                    null::text as course_code,
                    e.institute_id,
                    i.code as institute_code,
                    null::text as source_title,
                    null::text as source_url
                from events e
                left join institutes i on i.id = e.institute_id
                {event_scope}
                {event_filter}
                union all
                select
                    n.id,
                    'notification'::text as item_type,
                    n.title,
                    coalesce(n.deadline, n.event_date, n.start_date, n.created_at) as starts_at,
                    n.end_date as ends_at,
                    c.course_code,
                    n.institute_id,
                    i.code as institute_code,
                    n.source_title,
                    n.source_url
                from notifications n
                left join courses c on c.id = n.course_id
                left join institutes i on i.id = n.institute_id
                {notification_scope}
                {notification_filter}
                {notification_time_filter}
            )
            select *
            from upcoming
            order by starts_at, title
            limit 10
            """,
            tuple(params),
        )
        return [dict(row) for row in rows]

    async def _admin_institute_scope(
        self,
        current_user: AuthenticatedUser,
    ) -> uuid.UUID | object | None:
        roles = set(current_user.roles)
        if "global_admin" in roles:
            return None
        if not roles.intersection(ADMIN_ROLES):
            return _NO_ADMIN_SCOPE

        if current_user.institute and current_user.institute.get("id"):
            return current_user.institute["id"]

        code = self._institute_code_from_admin_email(current_user.email)
        if code is None:
            return _NO_ADMIN_SCOPE
        row = await self._fetchone("select id from institutes where code = %s", (code,))
        return row["id"] if row else _NO_ADMIN_SCOPE

    def _institute_code_from_admin_email(self, email: str) -> str | None:
        local_part = email.split("@", 1)[0].lower()
        for prefix, code in ADMIN_INSTITUTE_CODE_BY_EMAIL_PREFIX.items():
            if local_part.startswith(prefix):
                return code
        return None

    def _student_scope_clause(
        self,
        scope: uuid.UUID | None,
        alias: str,
    ) -> tuple[str, list[Any]]:
        if scope is None:
            return "", []
        return f"where {alias}.institute_id = %s", [scope]

    def _audience_scope_clause(
        self,
        scope: uuid.UUID | None,
        alias: str,
    ) -> tuple[str, list[Any]]:
        if scope is None:
            return "", []
        return (
            f"where ({alias}.institute_id = %s or {alias}.institute_id is null "
            f"or {alias}.target_scope = 'all')",
            [scope],
        )

    def _empty_dashboard(self, *, kind: str) -> dict[str, Any]:
        return {
            "scope": {"kind": kind, "institute_id": None, "institute_code": None},
            "overview": {},
            "ticket_counts_by_status": [{"key": key, "count": 0} for key in TICKET_STATUSES],
            "ticket_counts_by_priority": [{"key": key, "count": 0} for key in TICKET_PRIORITIES],
            "student_counts_by_institute": [],
            "recent_tickets": [],
            "upcoming_items": [],
        }

    async def _count(self, query: str, params: tuple[Any, ...]) -> int:
        row = await self._fetchone(query, params)
        return int(row["count"]) if row else 0

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


_NO_ADMIN_SCOPE = object()
