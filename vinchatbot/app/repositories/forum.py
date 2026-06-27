from __future__ import annotations

import json
import uuid
from typing import Any

from psycopg_pool import AsyncConnectionPool

from vinchatbot.app.schemas.forum import (
    CreateCommentRequest,
    CreateReportRequest,
    CreateTopicRequest,
    ModerateCommentRequest,
    ModerateTopicRequest,
)

# Returned by add_comment when the topic is locked (route maps it to 403).
LOCKED = object()

_TOPIC_CORE = """
    t.id,
    t.category_id,
    cat.slug as category_slug,
    cat.name_en as category_name_en,
    cat.name_vi as category_name_vi,
    t.author_user_id,
    coalesce(author.preferred_name, author.full_name) as author_name,
    t.title,
    t.content,
    t.tags,
    t.is_pinned,
    t.is_locked,
    (t.official_comment_id is not null) as has_official_answer,
    t.view_count,
    t.created_at,
    t.updated_at,
    t.last_activity_at,
    (
        select count(*) from forum_comments fc
        where fc.topic_id = t.id and fc.deleted = false
    ) as comment_count,
    (
        select coalesce(sum(v.value), 0) from forum_votes v
        where v.target_type = 'topic' and v.target_id = t.id
    ) as score,
    coalesce(
        (
            select v.value from forum_votes v
            where v.target_type = 'topic' and v.target_id = t.id and v.user_id = %s
        ),
        0
    ) as my_vote
"""

_COMMENT_SELECT = """
    select
        c.id,
        c.topic_id,
        c.parent_comment_id,
        c.author_user_id,
        coalesce(author.preferred_name, author.full_name) as author_name,
        c.content,
        c.is_official,
        c.deleted,
        c.created_at,
        c.updated_at,
        (
            select coalesce(sum(v.value), 0) from forum_votes v
            where v.target_type = 'comment' and v.target_id = c.id
        ) as score,
        coalesce(
            (
                select v.value from forum_votes v
                where v.target_type = 'comment' and v.target_id = c.id and v.user_id = %s
            ),
            0
        ) as my_vote
    from forum_comments c
    left join users author on author.id = c.author_user_id
"""


class ForumRepository:
    """Repository for the public discussion forum (topics, comments, votes, mentions)."""

    def __init__(self, pool: AsyncConnectionPool):
        self.pool = pool

    # ---- Categories --------------------------------------------------------

    async def list_categories(self) -> list[dict[str, Any]]:
        rows = await self._fetchall(
            """
            select
                cat.id,
                cat.slug,
                cat.name_en,
                cat.name_vi,
                cat.description_en,
                cat.description_vi,
                cat.color,
                cat.sort_order,
                cat.is_active,
                (
                    select count(*) from forum_topics t
                    where t.category_id = cat.id and t.deleted = false
                ) as topic_count
            from forum_categories cat
            where cat.is_active = true
            order by cat.sort_order, cat.name_en
            """,
            (),
        )
        return [dict(row) for row in rows]

    # ---- Topics ------------------------------------------------------------

    async def list_topics(
        self,
        *,
        user_id: uuid.UUID,
        category_slug: str | None = None,
        sort: str = "active",
        search: str | None = None,
    ) -> list[dict[str, Any]]:
        clauses = ["t.deleted = false"]
        params: list[Any] = [user_id]
        if category_slug:
            clauses.append("cat.slug = %s")
            params.append(category_slug)
        if search and search.strip():
            clauses.append("(t.title ilike %s or t.content ilike %s)")
            like = f"%{search.strip()}%"
            params.extend([like, like])

        if sort == "new":
            order = "t.is_pinned desc, t.created_at desc"
        elif sort == "top":
            order = "t.is_pinned desc, score desc, t.created_at desc"
        else:  # "active" (default)
            order = "t.is_pinned desc, t.last_activity_at desc"

        rows = await self._fetchall(
            f"""
            select {_TOPIC_CORE}
            from forum_topics t
            join forum_categories cat on cat.id = t.category_id
            left join users author on author.id = t.author_user_id
            where {" and ".join(clauses)}
            order by {order}
            """,
            tuple(params),
        )
        return [self._topic_from_row(row) for row in rows]

    async def get_topic(
        self,
        *,
        topic_id: uuid.UUID,
        user_id: uuid.UUID,
        bump_views: bool = False,
        include_deleted: bool = False,
    ) -> dict[str, Any] | None:
        if bump_views:
            await self._execute(
                "update forum_topics set view_count = view_count + 1 where id = %s and deleted = false",
                (topic_id,),
            )
        deleted_clause = "" if include_deleted else " and t.deleted = false"
        row = await self._fetchone(
            f"""
            select {_TOPIC_CORE}, t.attachments, t.official_comment_id
            from forum_topics t
            join forum_categories cat on cat.id = t.category_id
            left join users author on author.id = t.author_user_id
            where t.id = %s{deleted_clause}
            """,
            (user_id, topic_id),
        )
        if row is None:
            return None
        topic = self._topic_from_row(row)
        topic["attachments"] = row.get("attachments") or []
        topic["official_comment_id"] = row.get("official_comment_id")
        topic["comments"] = await self._comment_tree(topic_id, user_id)
        return topic

    async def list_comments(
        self,
        *,
        topic_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> list[dict[str, Any]] | None:
        topic = await self._fetchone(
            "select id from forum_topics where id = %s and deleted = false",
            (topic_id,),
        )
        if topic is None:
            return None
        return await self._comment_tree(topic_id, user_id)

    async def create_topic(
        self,
        *,
        author_user_id: uuid.UUID,
        request: CreateTopicRequest,
    ) -> dict[str, Any] | None:
        category_id = await self._resolve_category_id(request)
        if category_id is None:
            return None
        attachments_json = json.dumps([a.model_dump() for a in request.attachments])
        async with self.pool.connection() as conn:
            async with conn.transaction():
                cursor = await conn.execute(
                    """
                    insert into forum_topics (
                        category_id, author_user_id, title, content, tags, attachments
                    )
                    values (%s, %s, %s, %s, %s, %s::jsonb)
                    returning id
                    """,
                    (
                        category_id,
                        author_user_id,
                        request.title,
                        request.content,
                        request.tags,
                        attachments_json,
                    ),
                )
                topic_id = (await cursor.fetchone())["id"]
                await self._record_mentions_and_notify(
                    conn,
                    actor_id=author_user_id,
                    topic_id=topic_id,
                    comment_id=None,
                    topic_title=request.title,
                    topic_author_id=author_user_id,
                    parent_comment_author_id=None,
                    mentioned_user_ids=request.mentioned_user_ids,
                )
        return await self.get_topic(topic_id=topic_id, user_id=author_user_id)

    async def moderate_topic(
        self,
        *,
        topic_id: uuid.UUID,
        request: ModerateTopicRequest,
        mod_user_id: uuid.UUID,
    ) -> dict[str, Any] | None:
        existing = await self._fetchone(
            "select id from forum_topics where id = %s",
            (topic_id,),
        )
        if existing is None:
            return None

        fields: list[str] = []
        params: list[Any] = []
        changed = request.model_fields_set
        if "is_pinned" in changed:
            fields.append("is_pinned = %s")
            params.append(request.is_pinned)
        if "is_locked" in changed:
            fields.append("is_locked = %s")
            params.append(request.is_locked)
        if "deleted" in changed:
            fields.append("deleted = %s")
            params.append(request.deleted)
        if "official_comment_id" in changed:
            fields.append("official_comment_id = %s")
            params.append(request.official_comment_id)

        if fields:
            await self._execute(
                f"update forum_topics set {', '.join(fields)} where id = %s",
                (*params, topic_id),
            )
            if "official_comment_id" in changed and request.official_comment_id is not None:
                await self._execute(
                    "update forum_comments set is_official = (id = %s) where topic_id = %s",
                    (request.official_comment_id, topic_id),
                )

        return await self.get_topic(
            topic_id=topic_id,
            user_id=mod_user_id,
            include_deleted=True,
        )

    # ---- Comments ----------------------------------------------------------

    async def add_comment(
        self,
        *,
        topic_id: uuid.UUID,
        author_user_id: uuid.UUID,
        request: CreateCommentRequest,
    ) -> dict[str, Any] | None | object:
        topic = await self._fetchone(
            "select id, title, author_user_id, is_locked, deleted from forum_topics where id = %s",
            (topic_id,),
        )
        if topic is None or topic["deleted"]:
            return None
        if topic["is_locked"]:
            return LOCKED

        parent_author_id: uuid.UUID | None = None
        if request.parent_comment_id is not None:
            parent = await self._fetchone(
                """
                select id, author_user_id
                from forum_comments
                where id = %s and topic_id = %s and deleted = false
                """,
                (request.parent_comment_id, topic_id),
            )
            if parent is None:
                return None
            parent_author_id = parent["author_user_id"]

        async with self.pool.connection() as conn:
            async with conn.transaction():
                cursor = await conn.execute(
                    """
                    insert into forum_comments (topic_id, author_user_id, parent_comment_id, content)
                    values (%s, %s, %s, %s)
                    returning id
                    """,
                    (topic_id, author_user_id, request.parent_comment_id, request.content),
                )
                comment_id = (await cursor.fetchone())["id"]
                await conn.execute(
                    "update forum_topics set last_activity_at = now() where id = %s",
                    (topic_id,),
                )
                await self._record_mentions_and_notify(
                    conn,
                    actor_id=author_user_id,
                    topic_id=topic_id,
                    comment_id=comment_id,
                    topic_title=topic["title"],
                    topic_author_id=topic["author_user_id"],
                    parent_comment_author_id=parent_author_id,
                    mentioned_user_ids=request.mentioned_user_ids,
                )
        return await self._get_comment(comment_id, author_user_id)

    async def moderate_comment(
        self,
        *,
        comment_id: uuid.UUID,
        request: ModerateCommentRequest,
        mod_user_id: uuid.UUID,
    ) -> dict[str, Any] | None:
        comment = await self._fetchone(
            "select id, topic_id from forum_comments where id = %s",
            (comment_id,),
        )
        if comment is None:
            return None
        topic_id = comment["topic_id"]

        async with self.pool.connection() as conn:
            async with conn.transaction():
                changed = request.model_fields_set
                if "deleted" in changed:
                    await conn.execute(
                        "update forum_comments set deleted = %s where id = %s",
                        (request.deleted, comment_id),
                    )
                if "is_official" in changed:
                    if request.is_official:
                        await conn.execute(
                            "update forum_comments set is_official = false where topic_id = %s",
                            (topic_id,),
                        )
                        await conn.execute(
                            "update forum_comments set is_official = true where id = %s",
                            (comment_id,),
                        )
                        await conn.execute(
                            "update forum_topics set official_comment_id = %s where id = %s",
                            (comment_id, topic_id),
                        )
                    else:
                        await conn.execute(
                            "update forum_comments set is_official = false where id = %s",
                            (comment_id,),
                        )
                        await conn.execute(
                            """
                            update forum_topics set official_comment_id = null
                            where id = %s and official_comment_id = %s
                            """,
                            (topic_id, comment_id),
                        )
        return await self._get_comment(comment_id, mod_user_id)

    # ---- Votes -------------------------------------------------------------

    async def set_vote(
        self,
        *,
        user_id: uuid.UUID,
        target_type: str,
        target_id: uuid.UUID,
        value: int,
    ) -> dict[str, Any] | None:
        if not await self._vote_target_exists(target_type, target_id):
            return None

        if value == 0:
            await self._execute(
                """
                delete from forum_votes
                where user_id = %s and target_type = %s and target_id = %s
                """,
                (user_id, target_type, target_id),
            )
        else:
            await self._execute(
                """
                insert into forum_votes (user_id, target_type, target_id, value)
                values (%s, %s, %s, %s)
                on conflict (user_id, target_type, target_id)
                do update set value = excluded.value
                """,
                (user_id, target_type, target_id, value),
            )

        score_row = await self._fetchone(
            """
            select coalesce(sum(value), 0) as score
            from forum_votes
            where target_type = %s and target_id = %s
            """,
            (target_type, target_id),
        )
        return {
            "target_type": target_type,
            "target_id": target_id,
            "score": int(score_row["score"]) if score_row else 0,
            "my_vote": value,
        }

    # ---- Reports -----------------------------------------------------------

    async def create_report(
        self,
        *,
        reporter_user_id: uuid.UUID,
        request: CreateReportRequest,
    ) -> dict[str, Any] | None:
        if not await self._vote_target_exists(request.target_type, request.target_id):
            return None
        row = await self._fetchone(
            """
            insert into forum_reports (reporter_user_id, target_type, target_id, reason)
            values (%s, %s, %s, %s)
            returning id, reporter_user_id, target_type, target_id, reason, status, created_at
            """,
            (reporter_user_id, request.target_type, request.target_id, request.reason),
        )
        return dict(row) if row else None

    # ---- Members (for @mention autocomplete) -------------------------------

    async def search_members(self, query: str, *, limit: int = 8) -> list[dict[str, Any]]:
        term = query.strip()
        if not term:
            return []
        like = f"%{term}%"
        rows = await self._fetchall(
            """
            select id, full_name, preferred_name, email
            from users
            where status = 'active'
              and (full_name ilike %s or preferred_name ilike %s or email ilike %s)
            order by full_name
            limit %s
            """,
            (like, like, like, limit),
        )
        return [dict(row) for row in rows]

    # ---- Internal helpers --------------------------------------------------

    async def _resolve_category_id(self, request: CreateTopicRequest) -> uuid.UUID | None:
        if request.category_id is not None:
            row = await self._fetchone(
                "select id from forum_categories where id = %s and is_active = true",
                (request.category_id,),
            )
            return row["id"] if row else None
        if request.category_slug:
            row = await self._fetchone(
                "select id from forum_categories where slug = %s and is_active = true",
                (request.category_slug,),
            )
            return row["id"] if row else None
        return None

    async def _vote_target_exists(self, target_type: str, target_id: uuid.UUID) -> bool:
        table = "forum_topics" if target_type == "topic" else "forum_comments"
        row = await self._fetchone(
            f"select id from {table} where id = %s and deleted = false",
            (target_id,),
        )
        return row is not None

    async def _comment_tree(
        self,
        topic_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> list[dict[str, Any]]:
        rows = await self._fetchall(
            f"""
            {_COMMENT_SELECT}
            where c.topic_id = %s
            order by c.created_at asc, c.id asc
            """,
            (user_id, topic_id),
        )
        nodes: dict[uuid.UUID, dict[str, Any]] = {}
        roots: list[dict[str, Any]] = []
        for row in rows:
            node = self._comment_from_row(row)
            nodes[node["id"]] = node
        for row in rows:
            node = nodes[row["id"]]
            parent_id = row["parent_comment_id"]
            if parent_id is not None and parent_id in nodes:
                nodes[parent_id]["replies"].append(node)
            else:
                roots.append(node)
        return roots

    async def _get_comment(
        self,
        comment_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> dict[str, Any] | None:
        row = await self._fetchone(
            f"{_COMMENT_SELECT} where c.id = %s",
            (user_id, comment_id),
        )
        return self._comment_from_row(row) if row else None

    async def _record_mentions_and_notify(
        self,
        conn: Any,
        *,
        actor_id: uuid.UUID,
        topic_id: uuid.UUID,
        comment_id: uuid.UUID | None,
        topic_title: str,
        topic_author_id: uuid.UUID | None,
        parent_comment_author_id: uuid.UUID | None,
        mentioned_user_ids: list[uuid.UUID],
    ) -> None:
        valid_ids = await self._valid_mention_ids(conn, mentioned_user_ids, actor_id)
        for uid in valid_ids:
            await conn.execute(
                """
                insert into forum_mentions (topic_id, comment_id, mentioned_user_id, created_by)
                values (%s, %s, %s, %s)
                """,
                (topic_id if comment_id is None else None, comment_id, uid, actor_id),
            )

        actor_name = await self._display_name(conn, actor_id)
        quoted = topic_title if len(topic_title) <= 80 else topic_title[:77] + "..."
        on_comment = comment_id is not None

        # recipient_id -> (title, message). Mentions take precedence over reply notifications.
        recipients: dict[uuid.UUID, tuple[str, str]] = {}
        for uid in valid_ids:
            message = (
                f'{actor_name} mentioned you in a comment on "{quoted}".'
                if on_comment
                else f'{actor_name} mentioned you in "{quoted}".'
            )
            recipients[uid] = ("You were mentioned", message)

        if on_comment:
            if (
                parent_comment_author_id is not None
                and parent_comment_author_id != actor_id
                and parent_comment_author_id not in recipients
            ):
                recipients[parent_comment_author_id] = (
                    "New reply",
                    f'{actor_name} replied to your comment on "{quoted}".',
                )
            elif (
                parent_comment_author_id is None
                and topic_author_id is not None
                and topic_author_id != actor_id
                and topic_author_id not in recipients
            ):
                recipients[topic_author_id] = (
                    "New reply",
                    f'{actor_name} commented on your topic "{quoted}".',
                )

        for uid, (title, message) in recipients.items():
            await conn.execute(
                """
                insert into notifications (
                    type, title, message, priority, status, target_scope,
                    recipient_user_id, forum_topic_id, forum_comment_id, created_by
                )
                values ('forum', %s, %s, 'medium', 'published', 'student', %s, %s, %s, %s)
                """,
                (title, message, uid, topic_id, comment_id, actor_id),
            )

    async def _valid_mention_ids(
        self,
        conn: Any,
        mentioned_user_ids: list[uuid.UUID],
        actor_id: uuid.UUID,
    ) -> list[uuid.UUID]:
        if not mentioned_user_ids:
            return []
        seen: set[uuid.UUID] = set()
        unique = [uid for uid in mentioned_user_ids if not (uid in seen or seen.add(uid))]
        cursor = await conn.execute(
            "select id from users where id = any(%s) and status = 'active'",
            (unique,),
        )
        rows = await cursor.fetchall()
        present = {row["id"] for row in rows}
        return [uid for uid in unique if uid in present and uid != actor_id]

    async def _display_name(self, conn: Any, user_id: uuid.UUID) -> str:
        cursor = await conn.execute(
            "select coalesce(preferred_name, full_name) as name from users where id = %s",
            (user_id,),
        )
        row = await cursor.fetchone()
        return row["name"] if row and row["name"] else "Someone"

    def _excerpt(self, content: str) -> str:
        text = " ".join((content or "").split())
        return text[:197] + "..." if len(text) > 200 else text

    def _topic_from_row(self, row: dict[str, Any]) -> dict[str, Any]:
        data = dict(row)
        data["excerpt"] = self._excerpt(data.get("content") or "")
        data["tags"] = list(data.get("tags") or [])
        return data

    def _comment_from_row(self, row: dict[str, Any]) -> dict[str, Any]:
        data = dict(row)
        data["replies"] = []
        if data.get("deleted"):
            data["content"] = "[removed]"
            data["author_name"] = None
        return data

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
