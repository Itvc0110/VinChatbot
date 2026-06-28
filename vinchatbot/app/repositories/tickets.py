from __future__ import annotations

import uuid
from typing import Any

from psycopg import sql
from psycopg_pool import AsyncConnectionPool

from vinchatbot.app.repositories.auth import AuthenticatedUser
from vinchatbot.app.schemas.tickets import (
    AddTicketMessageRequest,
    AdminTicketFilters,
    AdminUpdateTicketRequest,
    CreateTicketRequest,
)

ADMIN_INSTITUTE_CODE_BY_EMAIL_PREFIX = {
    "admin.business": "VIB",
    "admin.cecs": "CECS",
    "admin.health": "CHS",
    "admin.liberal": "CASE",
}
ADMIN_ROLES = {"global_admin", "institute_admin", "staff"}


class TicketRepository:
    """Repository for student/admin support tickets with DB-level scoping."""

    def __init__(self, pool: AsyncConnectionPool):
        self.pool = pool

    async def list_student_tickets(self, user_id: uuid.UUID) -> list[dict[str, Any]]:
        profile = await self._student_profile_for_user(user_id)
        if profile is None:
            return []
        rows = await self._fetchall(
            self._ticket_select_sql(
                """
                where t.student_profile_id = %s
                  and t.deleted = false
                order by t.updated_at desc, t.created_at desc
                """
            ),
            (profile["id"],),
        )
        return [self._ticket_from_row(row) for row in rows]

    async def get_student_ticket(
        self,
        *,
        ticket_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> dict[str, Any] | None:
        profile = await self._student_profile_for_user(user_id)
        if profile is None:
            return None
        ticket = await self._ticket_for_student(ticket_id, profile["id"])
        if ticket is None:
            return None
        return await self._ticket_detail(ticket)

    async def create_student_ticket(
        self,
        *,
        user_id: uuid.UUID,
        request: CreateTicketRequest,
    ) -> dict[str, Any] | None:
        profile = await self._student_profile_for_user(user_id)
        if profile is None:
            return None

        async with self.pool.connection() as conn:
            async with conn.transaction():
                row = await conn.execute(
                    """
                    insert into tickets (
                        student_profile_id,
                        institute_id,
                        subject,
                        body,
                        department,
                        category,
                        priority,
                        status,
                        confirmed_by_user,
                        created_by_ai,
                        include_chat_context,
                        included_context,
                        source_conversation_id,
                        origin_question,
                        submitted_at
                    )
                    values (
                        %s, %s, %s, %s, %s, %s, %s, 'submitted', true, %s,
                        %s, %s, %s, %s, now()
                    )
                    returning id
                    """,
                    (
                        profile["id"],
                        profile["institute_id"],
                        request.subject,
                        request.body,
                        request.department,
                        request.category,
                        request.priority,
                        request.created_by_ai,
                        request.include_chat_context,
                        request.included_context if request.include_chat_context else None,
                        request.source_conversation_id,
                        request.origin_question,
                    ),
                )
                ticket_id = (await row.fetchone())["id"]

        return await self.get_student_ticket(ticket_id=ticket_id, user_id=user_id)

    async def add_student_message(
        self,
        *,
        ticket_id: uuid.UUID,
        user_id: uuid.UUID,
        request: AddTicketMessageRequest,
    ) -> dict[str, Any] | None:
        profile = await self._student_profile_for_user(user_id)
        if profile is None:
            return None
        ticket = await self._ticket_for_student(ticket_id, profile["id"])
        if ticket is None:
            return None

        row = await self._fetchone(
            """
            insert into ticket_messages (ticket_id, sender_user_id, author_type, body)
            values (%s, %s, 'student', %s)
            returning id, ticket_id, sender_user_id, author_type, body, created_at
            """,
            (ticket_id, user_id, request.body),
        )
        return await self._message_with_sender(row) if row else None

    async def list_admin_tickets(
        self,
        *,
        current_user: AuthenticatedUser,
        filters: AdminTicketFilters,
    ) -> list[dict[str, Any]]:
        scope = await self._admin_institute_scope(current_user)
        if scope is _NO_ADMIN_SCOPE:
            return []

        clauses = ["t.deleted = false"]
        params: list[Any] = []
        if not filters.include_archived:
            clauses.append("t.archived = false")
        if filters.status:
            clauses.append("t.status = %s")
            params.append(filters.status)
        if filters.priority:
            clauses.append("t.priority = %s")
            params.append(filters.priority)
        if scope is not None:
            clauses.append("t.institute_id = %s")
            params.append(scope)

        where_clause = "where " + " and ".join(clauses)
        rows = await self._fetchall(
            self._ticket_select_sql(
                f"""
                {where_clause}
                order by t.updated_at desc, t.created_at desc
                """
            ),
            tuple(params),
        )
        return [self._ticket_from_row(row) for row in rows]

    async def get_admin_ticket(
        self,
        *,
        ticket_id: uuid.UUID,
        current_user: AuthenticatedUser,
    ) -> dict[str, Any] | None:
        ticket = await self._ticket_for_admin(ticket_id, current_user)
        if ticket is None:
            return None
        return await self._ticket_detail(ticket)

    async def update_admin_ticket(
        self,
        *,
        ticket_id: uuid.UUID,
        current_user: AuthenticatedUser,
        request: AdminUpdateTicketRequest,
    ) -> dict[str, Any] | None:
        existing = await self._ticket_for_admin(ticket_id, current_user)
        if existing is None:
            return None

        fields: list[sql.Composable] = []
        params: list[Any] = []
        changed = request.model_fields_set
        if "status" in changed:
            fields.append(sql.SQL("status = %s"))
            params.append(request.status)
        if "priority" in changed:
            fields.append(sql.SQL("priority = %s"))
            params.append(request.priority)
        if "assigned_admin_id" in changed:
            fields.append(sql.SQL("assigned_admin_id = %s"))
            params.append(request.assigned_admin_id)
        if "resolution" in changed:
            fields.append(sql.SQL("resolution = %s"))
            params.append(request.resolution)
        if "archived" in changed:
            fields.append(sql.SQL("archived = %s"))
            params.append(request.archived)

        status_changed = "status" in changed and request.status != existing["status"]
        async with self.pool.connection() as conn:
            async with conn.transaction():
                if fields:
                    fields.append(sql.SQL("updated_at = now()"))
                    query = sql.SQL("update tickets set {} where id = %s").format(
                        sql.SQL(", ").join(fields)
                    )
                    await conn.execute(query, (*params, ticket_id))
                if status_changed:
                    await conn.execute(
                        """
                        insert into ticket_status_history (
                            ticket_id, old_status, new_status, changed_by
                        )
                        values (%s, %s, %s, %s)
                        """,
                        (ticket_id, existing["status"], request.status, current_user.id),
                    )

        return await self.get_admin_ticket(ticket_id=ticket_id, current_user=current_user)

    async def add_admin_message(
        self,
        *,
        ticket_id: uuid.UUID,
        current_user: AuthenticatedUser,
        request: AddTicketMessageRequest,
    ) -> dict[str, Any] | None:
        ticket = await self._ticket_for_admin(ticket_id, current_user)
        if ticket is None:
            return None

        row = await self._fetchone(
            """
            insert into ticket_messages (ticket_id, sender_user_id, author_type, body)
            values (%s, %s, 'admin', %s)
            returning id, ticket_id, sender_user_id, author_type, body, created_at
            """,
            (ticket_id, current_user.id, request.body),
        )
        return await self._message_with_sender(row) if row else None

    async def _ticket_for_student(
        self,
        ticket_id: uuid.UUID,
        student_profile_id: uuid.UUID,
    ) -> dict[str, Any] | None:
        row = await self._fetchone(
            self._ticket_select_sql(
                """
                where t.id = %s
                  and t.student_profile_id = %s
                  and t.deleted = false
                """
            ),
            (ticket_id, student_profile_id),
        )
        return self._ticket_from_row(row) if row else None

    async def _ticket_for_admin(
        self,
        ticket_id: uuid.UUID,
        current_user: AuthenticatedUser,
    ) -> dict[str, Any] | None:
        scope = await self._admin_institute_scope(current_user)
        if scope is _NO_ADMIN_SCOPE:
            return None

        if scope is None:
            row = await self._fetchone(
                self._ticket_select_sql("where t.id = %s and t.deleted = false"),
                (ticket_id,),
            )
        else:
            row = await self._fetchone(
                self._ticket_select_sql(
                    """
                    where t.id = %s
                      and t.institute_id = %s
                      and t.deleted = false
                    """
                ),
                (ticket_id, scope),
            )
        return self._ticket_from_row(row) if row else None

    async def _ticket_detail(self, ticket: dict[str, Any]) -> dict[str, Any]:
        return {
            **ticket,
            "messages": await self._ticket_messages(ticket["id"]),
            "status_history": await self._ticket_status_history(ticket["id"]),
        }

    async def _ticket_messages(self, ticket_id: uuid.UUID) -> list[dict[str, Any]]:
        rows = await self._fetchall(
            """
            select
                tm.id,
                tm.ticket_id,
                tm.sender_user_id,
                u.email as sender_email,
                u.full_name as sender_full_name,
                tm.author_type,
                tm.body,
                tm.created_at
            from ticket_messages tm
            left join users u on u.id = tm.sender_user_id
            where tm.ticket_id = %s
            order by tm.created_at, tm.id
            """,
            (ticket_id,),
        )
        return [dict(row) for row in rows]

    async def _ticket_status_history(self, ticket_id: uuid.UUID) -> list[dict[str, Any]]:
        rows = await self._fetchall(
            """
            select
                tsh.id,
                tsh.old_status,
                tsh.new_status,
                tsh.changed_by,
                u.email as changed_by_email,
                u.full_name as changed_by_full_name,
                tsh.changed_at
            from ticket_status_history tsh
            left join users u on u.id = tsh.changed_by
            where tsh.ticket_id = %s
            order by tsh.changed_at, tsh.id
            """,
            (ticket_id,),
        )
        return [dict(row) for row in rows]

    async def _message_with_sender(self, row: dict[str, Any]) -> dict[str, Any]:
        sender = None
        if row["sender_user_id"] is not None:
            sender = await self._fetchone(
                "select email, full_name from users where id = %s",
                (row["sender_user_id"],),
            )
        return {
            **dict(row),
            "sender_email": sender["email"] if sender else None,
            "sender_full_name": sender["full_name"] if sender else None,
        }

    async def _student_profile_for_user(self, user_id: uuid.UUID) -> dict[str, Any] | None:
        return await self._fetchone(
            """
            select id, institute_id
            from student_profiles
            where user_id = %s
            """,
            (user_id,),
        )

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

    def _ticket_select_sql(self, suffix: str) -> str:
        return f"""
            select
                t.id,
                t.student_profile_id,
                sp.student_id,
                student.full_name as student_name,
                t.institute_id,
                i.code as institute_code,
                t.subject,
                t.body,
                t.department,
                t.category,
                t.priority,
                t.status,
                t.confirmed_by_user,
                t.created_by_ai,
                t.include_chat_context,
                t.included_context,
                t.source_conversation_id,
                t.origin_question,
                t.assigned_admin_id,
                admin.full_name as assignee,
                t.submitted_at,
                t.due_at,
                t.sla_hours,
                t.resolution,
                t.archived,
                t.deleted,
                t.created_at,
                t.updated_at
            from tickets t
            join student_profiles sp on sp.id = t.student_profile_id
            join users student on student.id = sp.user_id
            left join institutes i on i.id = t.institute_id
            left join users admin on admin.id = t.assigned_admin_id
            {suffix}
        """

    def _ticket_from_row(self, row: dict[str, Any] | None) -> dict[str, Any] | None:
        return dict(row) if row else None

    async def _fetchone(self, query: Any, params: tuple[Any, ...]) -> dict[str, Any] | None:
        async with self.pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, params)
                return await cur.fetchone()

    async def _fetchall(self, query: Any, params: tuple[Any, ...]) -> list[dict[str, Any]]:
        async with self.pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, params)
                rows = await cur.fetchall()
        return list(rows)


_NO_ADMIN_SCOPE = object()
