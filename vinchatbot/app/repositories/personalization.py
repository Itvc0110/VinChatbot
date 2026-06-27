from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from psycopg_pool import AsyncConnectionPool

from vinchatbot.app.repositories.students import StudentRepository
from vinchatbot.app.schemas.personalization import (
    PersonalizationContext,
    PersonalizationConversation,
    PersonalizationCourse,
    PersonalizationDeadline,
    PersonalizationForumTopic,
    PersonalizationNotification,
    PersonalizationScheduleItem,
    PersonalizationStudentProfile,
    PersonalizationSuggestion,
)

MAX_CONTEXT_COURSES = 5
MAX_CONTEXT_SCHEDULE = 5
MAX_CONTEXT_DEADLINES = 5
MAX_CONTEXT_NOTIFICATIONS = 5
MAX_CONTEXT_SUGGESTIONS = 6
MAX_CONTEXT_FORUM_TOPICS = 4
MAX_CONTEXT_CONVERSATIONS = 3

# Hard ceiling for the rendered prompt block. Mirrors ChatRequest.backend_personalization_context's
# max_length so the server-built string can never grow the model input unboundedly.
MAX_PROMPT_CHARS = 6000


class PersonalizationRepository:
    """Build bounded, current-student-only context for personalized chat answers."""

    def __init__(self, pool: AsyncConnectionPool):
        self.pool = pool
        self.students = StudentRepository(pool)

    async def get_context(self, user_id: uuid.UUID) -> PersonalizationContext | None:
        profile = await self.students.get_current_student_profile(user_id)
        if profile is None:
            return None

        courses = await self.students.get_courses(profile["id"])
        schedule = await self.students.get_schedule(profile["id"], upcoming_only=True)
        deadlines = await self.students.get_deadlines(profile["id"], upcoming_only=True)
        notifications = await self.students.get_notifications(user_id=user_id, profile=profile)
        suggestions = await self.students.get_suggestions(user_id=user_id, profile=profile)
        forum_topics = await self._fetch_forum_topics(profile)
        recent_conversations = await self._fetch_recent_conversations(user_id)

        return PersonalizationContext(
            profile=PersonalizationStudentProfile(**profile),
            courses=[
                PersonalizationCourse(**course)
                for course in courses[:MAX_CONTEXT_COURSES]
            ],
            schedule=[
                PersonalizationScheduleItem(**item)
                for item in schedule[:MAX_CONTEXT_SCHEDULE]
            ],
            deadlines=[
                PersonalizationDeadline(**deadline)
                for deadline in deadlines[:MAX_CONTEXT_DEADLINES]
            ],
            notifications=[
                PersonalizationNotification(**notification)
                for notification in self._rank_notifications(notifications)[
                    :MAX_CONTEXT_NOTIFICATIONS
                ]
            ],
            suggestions=[
                PersonalizationSuggestion(**suggestion)
                for suggestion in suggestions[:MAX_CONTEXT_SUGGESTIONS]
            ],
            forum_topics=[
                PersonalizationForumTopic(**topic)
                for topic in forum_topics[:MAX_CONTEXT_FORUM_TOPICS]
            ],
            recent_conversations=[
                PersonalizationConversation(**conversation)
                for conversation in recent_conversations[:MAX_CONTEXT_CONVERSATIONS]
            ],
        )

    def _rank_notifications(self, notifications: list[dict[str, Any]]) -> list[dict[str, Any]]:
        priority_rank = {"urgent": 0, "high": 1, "medium": 2, "low": 3}
        visible = [notification for notification in notifications if not notification.get("archived")]
        return sorted(
            visible,
            key=lambda notification: (
                priority_rank.get(str(notification.get("priority") or "medium"), 2),
                notification.get("deadline") is None,
                notification.get("event_date") is None,
                notification.get("created_at"),
            ),
        )

    async def _fetch_forum_topics(self, profile: dict[str, Any]) -> list[dict[str, Any]]:
        if not await self._table_exists("forum_topics"):
            return []

        return await self._fetchall(
            """
            select
                t.id,
                t.title,
                cat.slug as category_slug,
                cat.name_en as category_name_en,
                t.is_pinned,
                t.last_activity_at
            from forum_topics t
            join forum_categories cat on cat.id = t.category_id
            left join student_profiles author_profile on author_profile.user_id = t.author_user_id
            where t.deleted = false
              and cat.is_active = true
              and (
                    author_profile.institute_id is null
                 or author_profile.institute_id = %s
              )
            order by t.is_pinned desc, t.last_activity_at desc, t.created_at desc
            limit %s
            """,
            (profile["institute"]["id"], MAX_CONTEXT_FORUM_TOPICS),
        )

    async def _fetch_recent_conversations(self, user_id: uuid.UUID) -> list[dict[str, Any]]:
        return await self._fetchall(
            """
            select id, title, topic, updated_at, last_message_at
            from conversations
            where user_id = %s
            order by coalesce(last_message_at, updated_at, created_at) desc, created_at desc
            limit %s
            """,
            (user_id, MAX_CONTEXT_CONVERSATIONS),
        )

    async def _table_exists(self, table_name: str) -> bool:
        row = await self._fetchone(
            """
            select exists (
                select 1
                from information_schema.tables
                where table_schema = current_schema()
                  and table_name = %s
            ) as exists
            """,
            (table_name,),
        )
        return bool(row and row["exists"])

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


def _fmt_dt(value: datetime | None) -> str:
    if value is None:
        return "n/a"
    return value.strftime("%Y-%m-%d %H:%M")


def _fmt_date(value: datetime | None) -> str:
    if value is None:
        return "n/a"
    return value.strftime("%Y-%m-%d")


def build_personalization_prompt(context: PersonalizationContext) -> str:
    """Render a bounded, plain-text snapshot of the student's own context for the agent.

    This block is built server-side from authenticated, current-student-only data and attached
    to the model input. It is advisory background only — the agent still grounds factual answers
    in retrieved sources. The output is capped at MAX_PROMPT_CHARS so it can never balloon the
    prompt regardless of how much demo data a student has.
    """
    profile = context.profile
    lines: list[str] = ["Student profile:"]
    program = profile.program or "n/a"
    major = f", major {profile.major}" if profile.major else ""
    lines.append(
        f"- {program}{major} at {profile.institute.code} ({profile.institute.name_en});"
        f" cohort {profile.cohort or 'n/a'}, academic year {profile.academic_year or 'n/a'};"
        f" preferred language {profile.preferred_language}."
    )
    summary = profile.academic_summary
    if summary is not None:
        gpa = f"{summary.gpa}" if summary.gpa is not None else "n/a"
        lines.append(
            f"- Academic standing: {summary.academic_status}; GPA {gpa};"
            f" credits {summary.credits_earned}/{summary.credits_required};"
            f" current semester {summary.current_semester or 'n/a'}."
        )

    if context.courses:
        lines.append("Current courses:")
        for course in context.courses:
            instructor = f" — {course.instructor}" if course.instructor else ""
            lines.append(f"- {course.course_code} {course.course_title}{instructor}")

    if context.schedule:
        lines.append("Next schedule items:")
        for item in context.schedule:
            where = item.room or item.location or ""
            where_str = f" @ {where}" if where else ""
            course = f" ({item.course_code})" if item.course_code else ""
            lines.append(f"- {_fmt_dt(item.start_time)} {item.title}{course}{where_str}")

    if context.deadlines:
        lines.append("Upcoming deadlines:")
        for deadline in context.deadlines:
            course = f" ({deadline.course_code})" if deadline.course_code else ""
            lines.append(f"- {_fmt_dt(deadline.due_at)} {deadline.title}{course}")

    if context.notifications:
        lines.append("Active notifications:")
        for notification in context.notifications:
            when = notification.deadline or notification.event_date
            when_str = f" (due {_fmt_date(when)})" if when else ""
            lines.append(f"- [{notification.priority}] {notification.title}{when_str}")

    if context.suggestions:
        lines.append("Smart suggestions:")
        for suggestion in context.suggestions:
            lines.append(f"- {suggestion.question_text}")

    if context.forum_topics:
        lines.append("Recent visible forum topics:")
        for topic in context.forum_topics:
            category = f" [{topic.category_name_en}]" if topic.category_name_en else ""
            lines.append(f"- {topic.title}{category}")

    if context.recent_conversations:
        lines.append("Recent conversations:")
        for conversation in context.recent_conversations:
            lines.append(f"- {conversation.title} (updated {_fmt_date(conversation.updated_at)})")

    rendered = "\n".join(lines)
    if len(rendered) > MAX_PROMPT_CHARS:
        rendered = rendered[: MAX_PROMPT_CHARS - 1].rstrip() + "…"
    return rendered
