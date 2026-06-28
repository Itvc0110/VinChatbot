from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from psycopg_pool import AsyncConnectionPool

MAX_STUDENT_SUGGESTIONS = 8
NEAR_DEADLINE_DAYS = 14

# Supported UI languages for content resolution. The base title/message/question_text
# columns hold the canonical English text, so an unspecified/invalid lang falls back to
# English here. The user-facing default language (Vietnamese) is chosen at the route layer.
SUPPORTED_LANGS = ("vi", "en")
DEFAULT_LANG = "en"


def normalize_lang(lang: str | None) -> str:
    """Clamp an arbitrary lang value to a supported suffix used in column names."""
    return lang if lang in SUPPORTED_LANGS else DEFAULT_LANG


def _pick(lang: str, vi: str, en: str) -> str:
    """Pick a Vietnamese or English variant for dynamically generated text."""
    return vi if lang == "vi" else en


class StudentRepository:
    """Read-only repository for current-student portal data."""

    def __init__(self, pool: AsyncConnectionPool):
        self.pool = pool

    async def get_current_student_profile(self, user_id: uuid.UUID) -> dict[str, Any] | None:
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
                i.name_en as institute_name_en,
                a.gpa,
                a.credits_earned,
                a.credits_required,
                a.current_semester,
                a.academic_status,
                a.updated_at as academic_summary_updated_at
            from student_profiles sp
            join institutes i on i.id = sp.institute_id
            left join academic_summaries a on a.student_profile_id = sp.id
            where sp.user_id = %s
            """,
            (user_id,),
        )
        if row is None:
            return None
        return self._student_profile_from_row(row)

    async def get_courses(self, student_profile_id: uuid.UUID) -> list[dict[str, Any]]:
        rows = await self._fetchall(
            """
            select
                c.id,
                c.course_code,
                c.course_title,
                c.credits,
                c.semester,
                c.academic_year,
                c.instructor,
                i.id as institute_id,
                i.code as institute_code,
                i.name_vi as institute_name_vi,
                i.name_en as institute_name_en
            from enrollments e
            join courses c on c.id = e.course_id
            left join institutes i on i.id = c.institute_id
            where e.student_profile_id = %s
            order by c.course_code
            """,
            (student_profile_id,),
        )
        return [self._course_from_row(row) for row in rows]

    async def get_schedule(
        self,
        student_profile_id: uuid.UUID,
        *,
        upcoming_only: bool = True,
    ) -> list[dict[str, Any]]:
        rows = await self._fetchall(
            """
            select
                s.id,
                s.course_id,
                c.course_code,
                c.course_title,
                s.title,
                s.schedule_type,
                s.start_time,
                s.end_time,
                s.location,
                s.building,
                s.room,
                s.instructor,
                s.recurrence_rule
            from schedules s
            left join courses c on c.id = s.course_id
            where s.student_profile_id = %s
              and (%s = false or s.end_time >= now())
            order by s.start_time, s.title
            """,
            (student_profile_id, upcoming_only),
        )
        return [dict(row) for row in rows]

    async def get_deadlines(
        self,
        student_profile_id: uuid.UUID,
        *,
        upcoming_only: bool = True,
    ) -> list[dict[str, Any]]:
        rows = await self._fetchall(
            """
            select
                d.id,
                d.course_id,
                c.course_code,
                c.course_title,
                d.title,
                d.kind,
                d.due_at,
                d.source_title,
                d.source_url
            from deadlines d
            left join courses c on c.id = d.course_id
            where d.student_profile_id = %s
              and (%s = false or d.due_at >= now())
            order by d.due_at, d.title
            """,
            (student_profile_id, upcoming_only),
        )
        return [dict(row) for row in rows]

    async def get_notifications(
        self,
        *,
        user_id: uuid.UUID,
        profile: dict[str, Any],
        lang: str = DEFAULT_LANG,
    ) -> list[dict[str, Any]]:
        suffix = normalize_lang(lang)
        course_ids = await self._fetch_enrolled_course_ids(profile["id"])
        forum_columns = await self._notification_forum_columns_available()
        forum_select = (
            "n.forum_topic_id, n.forum_comment_id"
            if forum_columns
            else "null::uuid as forum_topic_id, null::uuid as forum_comment_id"
        )
        student_scope_clause = (
            "or (n.target_scope = 'student' and n.recipient_user_id = %s)"
            if forum_columns
            else ""
        )
        params: list[Any] = [
            user_id,
            profile["institute"]["id"],
            course_ids,
            profile["cohort"],
        ]
        if forum_columns:
            params.append(user_id)

        rows = await self._fetchall(
            f"""
            select
                n.id,
                n.type,
                coalesce(n.title_{suffix}, n.title) as title,
                coalesce(n.message_{suffix}, n.message) as message,
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
                {forum_select},
                n.created_at,
                n.updated_at,
                (nr.id is not null) as is_read,
                coalesce(nr.important, false) as important,
                coalesce(nr.archived, false) as archived
            from notifications n
            left join institutes i on i.id = n.institute_id
            left join courses c on c.id = n.course_id
            left join notification_reads nr
                on nr.notification_id = n.id
               and nr.user_id = %s
            where n.status in ('published', 'scheduled')
              and (n.start_date is null or n.start_date <= now())
              and (n.end_date is null or n.end_date >= now())
              and (
                    n.target_scope = 'all'
                 or (n.target_scope = 'institute' and n.institute_id = %s)
                 or (n.target_scope = 'course' and n.course_id = any(%s))
                 or (n.target_scope = 'cohort' and n.cohort = %s)
                 {student_scope_clause}
              )
            order by n.priority desc, n.created_at desc, n.title
            """,
            tuple(params),
        )
        return [dict(row) for row in rows]

    async def mark_notification_read(
        self,
        *,
        notification_id: uuid.UUID,
        user_id: uuid.UUID,
        profile: dict[str, Any],
    ) -> dict[str, Any] | None:
        notification = await self.get_visible_notification(
            notification_id=notification_id,
            user_id=user_id,
            profile=profile,
        )
        if notification is None:
            return None

        await self._execute(
            """
            insert into notification_reads (notification_id, user_id, read_at)
            values (%s, %s, now())
            on conflict (notification_id, user_id) do update
            set read_at = excluded.read_at
            """,
            (notification_id, user_id),
        )
        return {"notification_id": notification_id, "is_read": True}

    async def mark_notification_unread(
        self,
        *,
        notification_id: uuid.UUID,
        user_id: uuid.UUID,
        profile: dict[str, Any],
    ) -> dict[str, Any] | None:
        notification = await self.get_visible_notification(
            notification_id=notification_id,
            user_id=user_id,
            profile=profile,
        )
        if notification is None:
            return None

        await self._execute(
            """
            delete from notification_reads
            where notification_id = %s
              and user_id = %s
            """,
            (notification_id, user_id),
        )
        return {"notification_id": notification_id, "is_read": False}

    async def mark_all_notifications_read(
        self,
        *,
        user_id: uuid.UUID,
        profile: dict[str, Any],
    ) -> int:
        notifications = await self.get_notifications(user_id=user_id, profile=profile)
        unread_ids = [
            notification["id"]
            for notification in notifications
            if not notification["is_read"] and not notification["archived"]
        ]
        for notification_id in unread_ids:
            await self._execute(
                """
                insert into notification_reads (notification_id, user_id, read_at)
                values (%s, %s, now())
                on conflict (notification_id, user_id) do update
                set read_at = excluded.read_at
                """,
                (notification_id, user_id),
            )
        return len(unread_ids)

    async def get_visible_notification(
        self,
        *,
        notification_id: uuid.UUID,
        user_id: uuid.UUID,
        profile: dict[str, Any],
    ) -> dict[str, Any] | None:
        course_ids = await self._fetch_enrolled_course_ids(profile["id"])
        forum_columns = await self._notification_forum_columns_available()
        student_scope_clause = (
            "or (n.target_scope = 'student' and n.recipient_user_id = %s)"
            if forum_columns
            else ""
        )
        params: list[Any] = [
            user_id,
            notification_id,
            profile["institute"]["id"],
            course_ids,
            profile["cohort"],
        ]
        if forum_columns:
            params.append(user_id)

        row = await self._fetchone(
            f"""
            select
                n.id,
                (nr.id is not null) as is_read
            from notifications n
            left join notification_reads nr
                on nr.notification_id = n.id
               and nr.user_id = %s
            where n.id = %s
              and n.status in ('published', 'scheduled')
              and (n.start_date is null or n.start_date <= now())
              and (n.end_date is null or n.end_date >= now())
              and (
                    n.target_scope = 'all'
                 or (n.target_scope = 'institute' and n.institute_id = %s)
                 or (n.target_scope = 'course' and n.course_id = any(%s))
                 or (n.target_scope = 'cohort' and n.cohort = %s)
                 {student_scope_clause}
              )
            """,
            tuple(params),
        )
        return dict(row) if row is not None else None

    async def get_suggestions(
        self,
        *,
        user_id: uuid.UUID,
        profile: dict[str, Any],
        lang: str = DEFAULT_LANG,
    ) -> list[dict[str, Any]]:
        lang = normalize_lang(lang)
        now = datetime.now(UTC)
        course_ids = await self._fetch_enrolled_course_ids(profile["id"])
        seeded_suggestions = await self._fetch_seeded_suggestions(profile, course_ids, lang)
        notifications = await self.get_notifications(user_id=user_id, profile=profile, lang=lang)
        deadlines = await self.get_deadlines(profile["id"], upcoming_only=True)
        schedule = await self.get_schedule(profile["id"], upcoming_only=True)
        forum_topics = await self._fetch_forum_topics_for_suggestions(profile)

        suggestions: list[dict[str, Any]] = []
        suggestions.extend(
            self._notification_suggestion(
                profile=profile, notification=notification, now=now, lang=lang
            )
            for notification in notifications
            if self._notification_can_influence_suggestions(
                notification=notification,
                profile=profile,
                course_ids=course_ids,
                now=now,
            )
        )
        suggestions.extend(
            self._deadline_suggestion(profile=profile, deadline=deadline, now=now, lang=lang)
            for deadline in deadlines
        )
        suggestions.extend(
            self._schedule_suggestion(profile=profile, schedule_item=item, now=now, lang=lang)
            for item in schedule
        )
        suggestions.extend(
            self._forum_topic_suggestion(profile=profile, topic=topic, now=now, lang=lang)
            for topic in forum_topics
            if self._forum_topic_can_influence_suggestions(topic)
        )
        suggestions.extend(seeded_suggestions)

        ranked = self._rank_and_dedupe_suggestions(suggestions)
        if len(ranked) < 3:
            ranked = self._rank_and_dedupe_suggestions(
                [*ranked, *self._fallback_suggestions(profile=profile, now=now, lang=lang)]
            )
        return ranked[:MAX_STUDENT_SUGGESTIONS]

    async def _fetch_seeded_suggestions(
        self,
        profile: dict[str, Any],
        course_ids: list[uuid.UUID],
        lang: str = DEFAULT_LANG,
    ) -> list[dict[str, Any]]:
        suffix = normalize_lang(lang)
        rows = await self._fetchall(
            f"""
            select
                sq.id,
                coalesce(sq.question_text_{suffix}, sq.question_text) as question_text,
                sq.source_type,
                sq.source_id,
                sq.notification_id,
                sq.topic,
                sq.intent,
                sq.category,
                sq.trigger_phase,
                sq.institute_id,
                i.code as institute_code,
                sq.course_id,
                c.course_code,
                sq.cohort,
                sq.score,
                sq.priority,
                sq.created_by_ai,
                sq.approved_by_admin,
                sq.is_active,
                sq.valid_from,
                sq.valid_until
            from suggested_questions sq
            left join institutes i on i.id = sq.institute_id
            left join courses c on c.id = sq.course_id
            where sq.is_active = true
              and (sq.valid_from is null or sq.valid_from <= now())
              and (sq.valid_until is null or sq.valid_until >= now())
              and (sq.institute_id is null or sq.institute_id = %s)
              and (sq.course_id is null or sq.course_id = any(%s))
              and (sq.cohort is null or sq.cohort = %s)
            order by sq.priority desc, sq.score desc, sq.question_text
            """,
            (profile["institute"]["id"], course_ids, profile["cohort"]),
        )
        return [dict(row) for row in rows]

    async def _fetch_forum_topics_for_suggestions(
        self,
        profile: dict[str, Any],
        *,
        limit: int = 6,
    ) -> list[dict[str, Any]]:
        rows = await self._fetchall(
            """
            select
                t.id,
                t.title,
                t.content,
                t.tags,
                t.is_pinned,
                t.is_locked,
                t.deleted,
                t.created_at,
                t.updated_at,
                t.last_activity_at,
                cat.slug as category_slug,
                cat.name_en as category_name_en,
                author_profile.institute_id as author_institute_id,
                author_institute.code as author_institute_code
            from forum_topics t
            join forum_categories cat on cat.id = t.category_id
            left join student_profiles author_profile on author_profile.user_id = t.author_user_id
            left join institutes author_institute on author_institute.id = author_profile.institute_id
            where t.deleted = false
              and cat.is_active = true
              and (
                    author_profile.institute_id is null
                 or author_profile.institute_id = %s
              )
            order by t.is_pinned desc, t.last_activity_at desc, t.created_at desc
            limit %s
            """,
            (profile["institute"]["id"], limit),
        )
        return [dict(row) for row in rows]

    def _notification_suggestion(
        self,
        *,
        profile: dict[str, Any],
        notification: dict[str, Any],
        now: datetime,
        lang: str = DEFAULT_LANG,
    ) -> dict[str, Any]:
        notification_type = str(notification.get("type") or "notification")
        default_title = _pick(lang, "thông báo này", "this announcement")
        title = str(notification.get("title") or default_title).strip()
        text_blob = f"{title} {notification.get('message') or ''}".lower()
        if "exam" in text_blob or "thi" in text_blob:
            question_text = _pick(
                lang,
                "Tôi cần lưu ý gì cho lịch thi của mình?",
                "What should I pay attention to for my exam schedule?",
            )
            category = "academic"
        elif "scholarship" in text_blob or "học bổng" in text_blob or "hoc bong" in text_blob:
            question_text = _pick(
                lang,
                "Học bổng này có yêu cầu và hạn nộp như thế nào?",
                "What are the requirements and deadline for this scholarship?",
            )
            category = "student_services"
        elif notification.get("deadline") is not None or notification_type == "deadline":
            question_text = _pick(
                lang, f"Tôi cần làm gì trước {title}?", f"What do I need to do before {title}?"
            )
            category = "deadline"
        elif notification.get("event_date") is not None or notification_type == "event":
            question_text = _pick(
                lang, f"Tôi cần biết gì về {title}?", f"What should I know about {title}?"
            )
            category = "event"
        else:
            question_text = _pick(
                lang, f"Tôi nên làm gì với {title}?", f"What should I do about {title}?"
            )
            category = notification_type

        trigger_phase = self._deadline_phase(notification.get("deadline"), now)
        if trigger_phase == "active":
            trigger_phase = "announcement"
        priority = self._notification_priority(notification)
        return self._suggestion_record(
            profile=profile,
            question_text=question_text,
            source_type="notification",
            source_id=notification["id"],
            notification_id=notification["id"],
            category=category,
            trigger_phase=trigger_phase,
            priority=priority,
            score=Decimal(priority) / Decimal("10"),
            valid_from=notification.get("start_date") or notification.get("created_at") or now,
            valid_until=(
                notification.get("end_date")
                or notification.get("deadline")
                or notification.get("event_date")
                or now + timedelta(days=30)
            ),
            topic=notification_type,
            intent="clarify_next_step",
            course_id=notification.get("course_id"),
            course_code=notification.get("course_code"),
            cohort=notification.get("cohort") or profile.get("cohort"),
        )

    def _deadline_suggestion(
        self,
        *,
        profile: dict[str, Any],
        deadline: dict[str, Any],
        now: datetime,
        lang: str = DEFAULT_LANG,
    ) -> dict[str, Any]:
        default_title = _pick(lang, "hạn chót tiếp theo", "my next deadline")
        title = str(deadline.get("title") or default_title).strip()
        due_at = deadline.get("due_at")
        trigger_phase = self._deadline_phase(due_at, now)
        priority = 86 if trigger_phase == "near_deadline" else 72
        return self._suggestion_record(
            profile=profile,
            question_text=_pick(
                lang,
                f"Tôi cần hoàn thành những gì trước {title}?",
                f"What do I need to finish before {title}?",
            ),
            source_type="deadline",
            source_id=deadline["id"],
            notification_id=None,
            category="deadline_context",
            trigger_phase=trigger_phase,
            priority=priority,
            score=Decimal(priority) / Decimal("10"),
            valid_from=now - timedelta(days=1),
            valid_until=due_at or now + timedelta(days=30),
            topic="deadline",
            intent="plan_next_step",
            course_id=deadline.get("course_id"),
            course_code=deadline.get("course_code"),
            cohort=profile.get("cohort"),
        )

    def _schedule_suggestion(
        self,
        *,
        profile: dict[str, Any],
        schedule_item: dict[str, Any],
        now: datetime,
        lang: str = DEFAULT_LANG,
    ) -> dict[str, Any]:
        default_title = _pick(lang, "lịch học của tôi", "my schedule")
        title = str(
            schedule_item.get("title") or schedule_item.get("course_title") or default_title
        )
        schedule_type = str(schedule_item.get("schedule_type") or "schedule")
        is_event = schedule_type in {"event", "workshop", "orientation"}
        return self._suggestion_record(
            profile=profile,
            question_text=(
                _pick(lang, f"Tôi cần biết gì trước {title}?", f"What should I know before {title}?")
                if is_event
                else _pick(
                    lang,
                    "Lịch học tuần này của tôi như thế nào?",
                    "What does my schedule look like this week?",
                )
            ),
            source_type="event" if is_event else "schedule",
            source_id=schedule_item["id"],
            notification_id=None,
            category="event" if is_event else "schedule_context",
            trigger_phase="upcoming_event" if is_event else "before_class",
            priority=68 if is_event else 64,
            score=Decimal("6.800") if is_event else Decimal("6.400"),
            valid_from=now - timedelta(days=1),
            valid_until=schedule_item.get("end_time") or now + timedelta(days=14),
            topic=schedule_type,
            intent="prepare",
            course_id=schedule_item.get("course_id"),
            course_code=schedule_item.get("course_code"),
            cohort=profile.get("cohort"),
        )

    def _forum_topic_suggestion(
        self,
        *,
        profile: dict[str, Any],
        topic: dict[str, Any],
        now: datetime,
        lang: str = DEFAULT_LANG,
    ) -> dict[str, Any]:
        default_title = _pick(lang, "chủ đề diễn đàn này", "this forum topic")
        title = str(topic.get("title") or default_title).strip()
        text_blob = f"{title} {topic.get('content') or ''} {' '.join(topic.get('tags') or [])}".lower()

        if "exam" in text_blob or "thi" in text_blob:
            question_text = _pick(
                lang,
                "Tôi nên chuẩn bị gì cho kỳ thi sắp tới?",
                "What should I prepare for upcoming exams?",
            )
            category = "academic"
            intent = "prepare_for_exam"
        elif "scholarship" in text_blob or "học bổng" in text_blob or "hoc bong" in text_blob:
            question_text = _pick(
                lang,
                "Tôi cần biết những hạn học bổng nào?",
                "What scholarship deadlines should I know about?",
            )
            category = "student_services"
            intent = "clarify_scholarship_deadlines"
        elif (
            "it" in text_blob
            or "wifi" in text_blob
            or "wi-fi" in text_blob
            or "portal" in text_blob
            or "login" in text_blob
        ):
            question_text = _pick(
                lang,
                "Làm sao để khắc phục các sự cố CNTT thường gặp của sinh viên?",
                "How do I fix common student IT issues?",
            )
            category = "student_services"
            intent = "resolve_it_issue"
        elif "registration" in text_blob or "add/drop" in text_blob or "advising" in text_blob:
            question_text = _pick(
                lang,
                "Tôi nên kiểm tra gì trước khi thay đổi đăng ký học phần?",
                "What should I check before changing my course registration?",
            )
            category = "academic"
            intent = "plan_registration"
        else:
            question_text = _pick(
                lang, f"Tôi cần biết gì về {title}?", f"What should I know about {title}?"
            )
            category = "forum"
            intent = "learn_from_forum_topic"

        priority = 78 if topic.get("is_pinned") else 62
        return self._suggestion_record(
            profile=profile,
            question_text=question_text,
            source_type="forum_topic",
            source_id=topic["id"],
            notification_id=None,
            category=category,
            trigger_phase="active",
            priority=priority,
            score=Decimal(priority) / Decimal("10"),
            valid_from=topic.get("created_at") or now - timedelta(days=1),
            valid_until=now + timedelta(days=21 if topic.get("is_pinned") else 10),
            topic=str(topic.get("category_slug") or "forum"),
            intent=intent,
            course_id=None,
            course_code=None,
            cohort=profile.get("cohort"),
        )

    def _fallback_suggestions(
        self, *, profile: dict[str, Any], now: datetime, lang: str = DEFAULT_LANG
    ) -> list[dict[str, Any]]:
        institute_code = profile["institute"]["code"]
        fallback_items = [
            (
                _pick(
                    lang,
                    "Tôi nên tập trung vào những hạn chót nào tiếp theo?",
                    "What deadlines should I focus on next?",
                ),
                "deadline_context",
                "deadline",
                42,
            ),
            (
                _pick(
                    lang,
                    "Tuần này lịch học của tôi có những gì?",
                    "What is on my academic schedule this week?",
                ),
                "schedule_context",
                "schedule",
                40,
            ),
            (
                _pick(
                    lang,
                    f"Tuần này sinh viên {institute_code} cần lưu ý điều gì?",
                    f"What should {institute_code} students pay attention to this week?",
                ),
                "academic",
                "static",
                38,
            ),
        ]
        return [
            self._suggestion_record(
                profile=profile,
                question_text=question_text,
                source_type=source_type,
                source_id=None,
                notification_id=None,
                category=category,
                trigger_phase="active",
                priority=priority,
                score=Decimal(priority) / Decimal("10"),
                valid_from=now - timedelta(days=1),
                valid_until=now + timedelta(days=14),
                topic=category,
                intent="general_support",
                course_id=None,
                course_code=None,
                cohort=profile.get("cohort"),
            )
            for question_text, category, source_type, priority in fallback_items
        ]

    def _suggestion_record(
        self,
        *,
        profile: dict[str, Any],
        question_text: str,
        source_type: str,
        source_id: uuid.UUID | None,
        notification_id: uuid.UUID | None,
        category: str,
        trigger_phase: str,
        priority: int,
        score: Decimal,
        valid_from: datetime | None,
        valid_until: datetime | None,
        topic: str,
        intent: str,
        course_id: uuid.UUID | None,
        course_code: str | None,
        cohort: int | None,
    ) -> dict[str, Any]:
        institute = profile["institute"]
        return {
            "id": self._suggestion_id(profile["id"], source_type, source_id, question_text),
            "question_text": question_text,
            "source_type": source_type,
            "source_id": source_id,
            "notification_id": notification_id,
            "topic": topic,
            "intent": intent,
            "category": category,
            "trigger_phase": trigger_phase,
            "institute_id": institute["id"],
            "institute_code": institute["code"],
            "course_id": course_id,
            "course_code": course_code,
            "cohort": cohort,
            "score": score,
            "priority": priority,
            "created_by_ai": True,
            "approved_by_admin": True,
            "is_active": True,
            "valid_from": valid_from,
            "valid_until": valid_until,
        }

    def _rank_and_dedupe_suggestions(self, suggestions: list[dict[str, Any]]) -> list[dict[str, Any]]:
        deduped: dict[str, dict[str, Any]] = {}
        for suggestion in suggestions:
            question_key = " ".join(str(suggestion["question_text"]).lower().split())
            existing = deduped.get(question_key)
            if existing is None or self._suggestion_sort_key(suggestion) < self._suggestion_sort_key(existing):
                deduped[question_key] = suggestion
        return sorted(deduped.values(), key=self._suggestion_sort_key)

    def _suggestion_sort_key(self, suggestion: dict[str, Any]) -> tuple[int, Decimal, str]:
        return (
            -int(suggestion.get("priority") or 0),
            -Decimal(str(suggestion.get("score") or "0")),
            str(suggestion.get("question_text") or ""),
        )

    def _deadline_phase(self, deadline_at: Any, now: datetime) -> str:
        deadline = self._aware_datetime(deadline_at)
        if deadline is None:
            return "active"
        if deadline < now:
            return "overdue"
        if deadline <= now + timedelta(days=NEAR_DEADLINE_DAYS):
            return "near_deadline"
        return "early"

    def _notification_priority(self, notification: dict[str, Any]) -> int:
        priority = str(notification.get("priority") or "medium")
        base = {
            "urgent": 100,
            "high": 92,
            "medium": 76,
            "low": 58,
        }.get(priority, 70)
        if notification.get("deadline") is not None:
            base += 4
        return base

    def _notification_can_influence_suggestions(
        self,
        *,
        notification: dict[str, Any],
        profile: dict[str, Any],
        course_ids: list[uuid.UUID],
        now: datetime,
    ) -> bool:
        if notification.get("archived"):
            return False
        if notification.get("status") not in {"published", "scheduled"}:
            return False
        start_date = self._aware_datetime(notification.get("start_date"))
        end_date = self._aware_datetime(notification.get("end_date"))
        if start_date is not None and start_date > now:
            return False
        if end_date is not None and end_date < now:
            return False

        target_scope = notification.get("target_scope")
        if target_scope == "all":
            return True
        if target_scope == "institute":
            return notification.get("institute_id") == profile["institute"]["id"]
        if target_scope == "course":
            return notification.get("course_id") in set(course_ids)
        if target_scope == "cohort":
            return notification.get("cohort") == profile.get("cohort")
        if target_scope == "student":
            return True
        return False

    def _forum_topic_can_influence_suggestions(self, topic: dict[str, Any]) -> bool:
        return bool(topic.get("id")) and not topic.get("deleted")

    def _aware_datetime(self, value: Any) -> datetime | None:
        if not isinstance(value, datetime):
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    def _suggestion_id(
        self,
        student_profile_id: uuid.UUID,
        source_type: str,
        source_id: uuid.UUID | None,
        question_text: str,
    ) -> uuid.UUID:
        return uuid.uuid5(
            uuid.NAMESPACE_URL,
            f"vinchatbot:suggestion:{student_profile_id}:{source_type}:{source_id}:{question_text}",
        )

    async def _fetch_enrolled_course_ids(self, student_profile_id: uuid.UUID) -> list[uuid.UUID]:
        rows = await self._fetchall(
            """
            select course_id
            from enrollments
            where student_profile_id = %s
            """,
            (student_profile_id,),
        )
        return [row["course_id"] for row in rows]

    async def _notification_forum_columns_available(self) -> bool:
        required = {"recipient_user_id", "forum_topic_id", "forum_comment_id"}
        rows = await self._fetchall(
            """
            select column_name
            from information_schema.columns
            where table_schema = current_schema()
              and table_name = 'notifications'
              and column_name = any(%s)
            """,
            (list(required),),
        )
        return required.issubset({row["column_name"] for row in rows})

    def _student_profile_from_row(self, row: dict[str, Any]) -> dict[str, Any]:
        academic_summary = None
        if row["academic_status"] is not None:
            academic_summary = {
                "gpa": row["gpa"],
                "credits_earned": row["credits_earned"],
                "credits_required": row["credits_required"],
                "current_semester": row["current_semester"],
                "academic_status": row["academic_status"],
                "updated_at": row["academic_summary_updated_at"],
            }

        return {
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
            "institute": {
                "id": row["institute_id"],
                "code": row["institute_code"],
                "name_vi": row["institute_name_vi"],
                "name_en": row["institute_name_en"],
            },
            "academic_summary": academic_summary,
        }

    def _course_from_row(self, row: dict[str, Any]) -> dict[str, Any]:
        institute = None
        if row["institute_id"] is not None:
            institute = {
                "id": row["institute_id"],
                "code": row["institute_code"],
                "name_vi": row["institute_name_vi"],
                "name_en": row["institute_name_en"],
            }
        return {
            "id": row["id"],
            "course_code": row["course_code"],
            "course_title": row["course_title"],
            "credits": row["credits"],
            "semester": row["semester"],
            "academic_year": row["academic_year"],
            "instructor": row["instructor"],
            "institute": institute,
        }

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
