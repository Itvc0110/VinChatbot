from __future__ import annotations

import uuid
from typing import Any

from psycopg import sql
from psycopg_pool import AsyncConnectionPool

from vinchatbot.app.repositories.auth import AuthenticatedUser
from vinchatbot.app.repositories.tickets import (
    ADMIN_INSTITUTE_CODE_BY_EMAIL_PREFIX,
    ADMIN_ROLES,
)
from vinchatbot.app.schemas.admin_notifications import (
    AdminNotificationCreateRequest,
    AdminNotificationScheduleRequest,
    AdminNotificationUpdateRequest,
)


class NotificationPermissionError(Exception):
    """Raised when an admin action targets outside the user's allowed institute scope."""


class AdminNotificationRepository:
    """Admin repository for notification lifecycle management."""

    def __init__(self, pool: AsyncConnectionPool):
        self.pool = pool

    async def list_target_institutes(
        self,
        current_user: AuthenticatedUser,
    ) -> list[dict[str, Any]]:
        scope = await self._admin_institute_scope(current_user)
        if scope is _NO_ADMIN_SCOPE:
            return []
        if scope is None:
            rows = await self._fetchall(
                """
                select id, code, name_vi, name_en
                from institutes
                order by code
                """,
                (),
            )
        else:
            rows = await self._fetchall(
                """
                select id, code, name_vi, name_en
                from institutes
                where id = %s
                order by code
                """,
                (scope,),
            )
        return [dict(row) for row in rows]

    async def list_notifications(
        self,
        current_user: AuthenticatedUser,
    ) -> list[dict[str, Any]]:
        scope = await self._admin_institute_scope(current_user)
        if scope is _NO_ADMIN_SCOPE:
            return []

        if scope is None:
            rows = await self._fetchall(
                self._notification_select_sql(
                    """
                    order by n.updated_at desc, n.created_at desc
                    """
                ),
                (),
            )
        else:
            rows = await self._fetchall(
                self._notification_select_sql(
                    """
                    where n.target_scope = 'institute'
                      and n.institute_id = %s
                    order by n.updated_at desc, n.created_at desc
                    """
                ),
                (scope,),
            )
        return [dict(row) for row in rows]

    async def get_notification(
        self,
        *,
        notification_id: uuid.UUID,
        current_user: AuthenticatedUser,
    ) -> dict[str, Any] | None:
        return await self._notification_for_admin(notification_id, current_user)

    async def create_notification(
        self,
        *,
        current_user: AuthenticatedUser,
        request: AdminNotificationCreateRequest,
    ) -> dict[str, Any]:
        await self._ensure_request_in_scope(current_user, request.target_scope, request.institute_id)
        row = await self._fetchone(
            """
            insert into notifications (
                type,
                title,
                message,
                title_vi,
                title_en,
                message_vi,
                message_en,
                priority,
                status,
                target_scope,
                institute_id,
                cohort,
                deadline,
                event_date,
                start_date,
                end_date,
                source_title,
                source_url,
                forum_topic_id,
                forum_comment_id,
                created_by
            )
            values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            returning id
            """,
            (
                request.type,
                request.title.strip(),
                request.message.strip(),
                request.title_vi,
                request.title_en,
                request.message_vi,
                request.message_en,
                request.priority,
                request.status,
                request.target_scope,
                request.institute_id,
                request.cohort,
                request.deadline,
                request.event_date,
                request.start_date,
                request.end_date,
                request.source_title,
                request.source_url,
                request.forum_topic_id,
                request.forum_comment_id,
                current_user.id,
            ),
        )
        return await self.get_notification(
            notification_id=row["id"],
            current_user=current_user,
        )

    async def update_notification(
        self,
        *,
        notification_id: uuid.UUID,
        current_user: AuthenticatedUser,
        request: AdminNotificationUpdateRequest,
    ) -> dict[str, Any] | None:
        existing = await self._notification_for_admin(notification_id, current_user)
        if existing is None:
            return None

        next_target_scope = (
            request.target_scope
            if "target_scope" in request.model_fields_set
            else existing["target_scope"]
        )
        next_institute_id = (
            request.institute_id
            if "institute_id" in request.model_fields_set
            else existing["institute_id"]
        )
        await self._ensure_request_in_scope(current_user, next_target_scope, next_institute_id)

        fields: list[sql.Composable] = []
        params: list[Any] = []
        field_names = {
            "type",
            "title",
            "message",
            "title_vi",
            "title_en",
            "message_vi",
            "message_en",
            "priority",
            "target_scope",
            "institute_id",
            "cohort",
            "deadline",
            "event_date",
            "start_date",
            "end_date",
            "source_title",
            "source_url",
            "forum_topic_id",
            "forum_comment_id",
        }
        for field_name in field_names.intersection(request.model_fields_set):
            fields.append(sql.SQL("{} = %s").format(sql.Identifier(field_name)))
            value = getattr(request, field_name)
            if isinstance(value, str) and field_name in {"title", "message"}:
                value = value.strip()
            params.append(value)

        if fields:
            fields.append(sql.SQL("updated_at = now()"))
            query = sql.SQL("update notifications set {} where id = %s").format(
                sql.SQL(", ").join(fields)
            )
            await self._execute(query, (*params, notification_id))

        return await self.get_notification(
            notification_id=notification_id,
            current_user=current_user,
        )

    async def publish_notification(
        self,
        *,
        notification_id: uuid.UUID,
        current_user: AuthenticatedUser,
    ) -> dict[str, Any] | None:
        existing = await self._notification_for_admin(notification_id, current_user)
        if existing is None:
            return None
        await self._execute(
            """
            update notifications
            set status = 'published',
                start_date = now(),
                updated_at = now()
            where id = %s
            """,
            (notification_id,),
        )
        return await self.get_notification(
            notification_id=notification_id,
            current_user=current_user,
        )

    async def schedule_notification(
        self,
        *,
        notification_id: uuid.UUID,
        current_user: AuthenticatedUser,
        request: AdminNotificationScheduleRequest,
    ) -> dict[str, Any] | None:
        existing = await self._notification_for_admin(notification_id, current_user)
        if existing is None:
            return None
        await self._execute(
            """
            update notifications
            set status = 'scheduled',
                start_date = %s,
                end_date = %s,
                updated_at = now()
            where id = %s
            """,
            (request.publish_at, request.end_date, notification_id),
        )
        return await self.get_notification(
            notification_id=notification_id,
            current_user=current_user,
        )

    async def archive_notification(
        self,
        *,
        notification_id: uuid.UUID,
        current_user: AuthenticatedUser,
    ) -> dict[str, Any] | None:
        existing = await self._notification_for_admin(notification_id, current_user)
        if existing is None:
            return None
        await self._execute(
            """
            update notifications
            set status = 'archived',
                updated_at = now()
            where id = %s
            """,
            (notification_id,),
        )
        return await self.get_notification(
            notification_id=notification_id,
            current_user=current_user,
        )

    async def _notification_for_admin(
        self,
        notification_id: uuid.UUID,
        current_user: AuthenticatedUser,
    ) -> dict[str, Any] | None:
        scope = await self._admin_institute_scope(current_user)
        if scope is _NO_ADMIN_SCOPE:
            return None
        if scope is None:
            row = await self._fetchone(
                self._notification_select_sql("where n.id = %s"),
                (notification_id,),
            )
        else:
            row = await self._fetchone(
                self._notification_select_sql(
                    """
                    where n.id = %s
                      and n.target_scope = 'institute'
                      and n.institute_id = %s
                    """
                ),
                (notification_id, scope),
            )
        return dict(row) if row else None

    async def _ensure_request_in_scope(
        self,
        current_user: AuthenticatedUser,
        target_scope: str,
        institute_id: uuid.UUID | None,
    ) -> None:
        scope = await self._admin_institute_scope(current_user)
        if scope is _NO_ADMIN_SCOPE:
            raise NotificationPermissionError
        if scope is None:
            return
        if target_scope != "institute" or institute_id != scope:
            raise NotificationPermissionError

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

    def _notification_select_sql(self, suffix: str) -> str:
        return f"""
            select
                n.id,
                n.type,
                n.title,
                n.message,
                n.title_vi,
                n.title_en,
                n.message_vi,
                n.message_en,
                n.priority,
                n.status,
                n.target_scope,
                n.institute_id,
                i.code as institute_code,
                n.course_id,
                c.course_code,
                n.cohort,
                n.deadline,
                n.event_date,
                n.start_date,
                n.end_date,
                n.source_title,
                n.source_url,
                n.forum_topic_id,
                n.forum_comment_id,
                n.created_by,
                creator.email as created_by_email,
                creator.full_name as created_by_name,
                n.created_at,
                n.updated_at
            from notifications n
            left join institutes i on i.id = n.institute_id
            left join courses c on c.id = n.course_id
            left join users creator on creator.id = n.created_by
            {suffix}
        """

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

    async def _execute(self, query: Any, params: tuple[Any, ...]) -> None:
        async with self.pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, params)


_NO_ADMIN_SCOPE = object()
