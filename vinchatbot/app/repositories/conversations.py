from __future__ import annotations

import uuid
from typing import Any

from psycopg import sql
from psycopg.types.json import Jsonb
from psycopg_pool import AsyncConnectionPool

from vinchatbot.app.schemas.conversations import (
    AppendMessageRequest,
    CreateConversationRequest,
    UpdateConversationRequest,
)

DEFAULT_CONVERSATION_TITLE = "New conversation"
DERIVED_TITLE_MAX_LENGTH = 64


class ConversationRepository:
    """Repository for user-owned chat conversations and messages."""

    def __init__(self, pool: AsyncConnectionPool):
        self.pool = pool

    async def list_conversations(self, user_id: uuid.UUID) -> list[dict[str, Any]]:
        rows = await self._fetchall(
            """
            select id, title, title_manual, topic, created_at, updated_at, last_message_at
            from conversations
            where user_id = %s
            order by coalesce(last_message_at, updated_at, created_at) desc, id desc
            """,
            (user_id,),
        )
        return [dict(row) for row in rows]

    async def create_conversation(
        self,
        *,
        user_id: uuid.UUID,
        request: CreateConversationRequest,
    ) -> dict[str, Any]:
        title = request.title or derive_conversation_title(request.initial_message)
        title_manual = request.title is not None
        row = await self._fetchone(
            """
            insert into conversations (user_id, title, title_manual, topic)
            values (%s, %s, %s, %s)
            returning id
            """,
            (user_id, title, title_manual, request.topic),
        )
        conversation_id = row["id"]

        if request.initial_message:
            await self.append_message(
                user_id=user_id,
                conversation_id=conversation_id,
                request=AppendMessageRequest(role="user", content=request.initial_message),
            )

        conversation = await self.get_conversation(user_id=user_id, conversation_id=conversation_id)
        if conversation is None:  # pragma: no cover - the row was just inserted for this user.
            raise RuntimeError("Conversation creation returned no row.")
        return conversation

    async def get_conversation(
        self,
        *,
        user_id: uuid.UUID,
        conversation_id: uuid.UUID,
    ) -> dict[str, Any] | None:
        conversation = await self._conversation_for_user(
            user_id=user_id,
            conversation_id=conversation_id,
        )
        if conversation is None:
            return None
        return {
            **conversation,
            "messages": await self.list_messages(
                user_id=user_id,
                conversation_id=conversation_id,
            ),
        }

    async def list_messages(
        self,
        *,
        user_id: uuid.UUID,
        conversation_id: uuid.UUID,
    ) -> list[dict[str, Any]] | None:
        if await self._conversation_for_user(user_id=user_id, conversation_id=conversation_id) is None:
            return None
        rows = await self._fetchall(
            """
            select
                id,
                conversation_id,
                role,
                content,
                answer_json,
                intent,
                topic,
                confidence,
                needs_human_review,
                created_at
            from messages
            where conversation_id = %s
            order by created_at, id
            """,
            (conversation_id,),
        )
        return [dict(row) for row in rows]

    async def update_conversation(
        self,
        *,
        user_id: uuid.UUID,
        conversation_id: uuid.UUID,
        request: UpdateConversationRequest,
    ) -> dict[str, Any] | None:
        if await self._conversation_for_user(user_id=user_id, conversation_id=conversation_id) is None:
            return None

        fields: list[sql.Composable] = []
        params: list[Any] = []
        changed = request.model_fields_set
        if "title" in changed:
            fields.append(sql.SQL("title = %s"))
            params.append(request.title or DEFAULT_CONVERSATION_TITLE)
            if "title_manual" not in changed:
                fields.append(sql.SQL("title_manual = true"))
        if "topic" in changed:
            fields.append(sql.SQL("topic = %s"))
            params.append(request.topic)
        if "title_manual" in changed:
            fields.append(sql.SQL("title_manual = %s"))
            params.append(request.title_manual)

        if fields:
            fields.append(sql.SQL("updated_at = now()"))
            query = sql.SQL("update conversations set {} where id = %s and user_id = %s").format(
                sql.SQL(", ").join(fields)
            )
            await self._execute(query, (*params, conversation_id, user_id))

        return await self.get_conversation(user_id=user_id, conversation_id=conversation_id)

    async def delete_conversation(
        self,
        *,
        user_id: uuid.UUID,
        conversation_id: uuid.UUID,
    ) -> bool:
        row = await self._fetchone(
            """
            delete from conversations
            where id = %s and user_id = %s
            returning id
            """,
            (conversation_id, user_id),
        )
        return row is not None

    async def append_message(
        self,
        *,
        user_id: uuid.UUID,
        conversation_id: uuid.UUID,
        request: AppendMessageRequest,
    ) -> dict[str, Any] | None:
        conversation = await self._conversation_for_user(
            user_id=user_id,
            conversation_id=conversation_id,
        )
        if conversation is None:
            return None

        async with self.pool.connection() as conn:
            async with conn.transaction():
                cursor = await conn.execute(
                    """
                    insert into messages (
                        conversation_id,
                        role,
                        content,
                        answer_json,
                        intent,
                        topic,
                        confidence,
                        needs_human_review
                    )
                    values (%s, %s, %s, %s, %s, %s, %s, %s)
                    returning
                        id,
                        conversation_id,
                        role,
                        content,
                        answer_json,
                        intent,
                        topic,
                        confidence,
                        needs_human_review,
                        created_at
                    """,
                    (
                        conversation_id,
                        request.role,
                        request.content,
                        Jsonb(request.answer_json) if request.answer_json is not None else None,
                        request.intent,
                        request.topic,
                        request.confidence,
                        request.needs_human_review,
                    ),
                )
                message = await cursor.fetchone()

                title_update = ""
                params: list[Any] = [message["created_at"], conversation_id, user_id]
                if (
                    request.role == "user"
                    and not conversation["title_manual"]
                    and conversation["title"] == DEFAULT_CONVERSATION_TITLE
                ):
                    title_update = ", title = %s"
                    params.insert(1, derive_conversation_title(request.content))

                await conn.execute(
                    f"""
                    update conversations
                    set last_message_at = %s,
                        updated_at = now()
                        {title_update}
                    where id = %s and user_id = %s
                    """,
                    tuple(params),
                )

        return dict(message)

    async def _conversation_for_user(
        self,
        *,
        user_id: uuid.UUID,
        conversation_id: uuid.UUID,
    ) -> dict[str, Any] | None:
        row = await self._fetchone(
            """
            select id, title, title_manual, topic, created_at, updated_at, last_message_at
            from conversations
            where id = %s and user_id = %s
            """,
            (conversation_id, user_id),
        )
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

    async def _execute(self, query: Any, params: tuple[Any, ...]) -> None:
        async with self.pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, params)


def derive_conversation_title(message: str | None) -> str:
    if not message:
        return DEFAULT_CONVERSATION_TITLE
    title = " ".join(message.split())
    if not title:
        return DEFAULT_CONVERSATION_TITLE
    if len(title) <= DERIVED_TITLE_MAX_LENGTH:
        return title
    return title[: DERIVED_TITLE_MAX_LENGTH - 3].rstrip() + "..."
