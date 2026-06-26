from __future__ import annotations

from collections import Counter

import pytest

from scripts import seed_demo_data


def test_demo_seed_plan_has_expected_user_counts():
    plan = seed_demo_data.build_seed_plan()

    assert len(plan.users) == 55
    assert len(plan.students) == 50
    assert len(plan.admins) == 5
    assert len(plan.student_profiles) == 50
    assert len(plan.academic_summaries) == 50


def test_demo_seed_plan_student_distribution():
    plan = seed_demo_data.build_seed_plan()

    assert plan.student_distribution() == {
        "VIB": 20,
        "CECS": 15,
        "CHS": 10,
        "CASE": 5,
    }


def test_demo_seed_plan_required_emails_are_present():
    plan = seed_demo_data.build_seed_plan()
    emails = {user.email for user in plan.users}

    assert {
        "student.business.demo@vinuni.edu.vn",
        "student.cs.demo@vinuni.edu.vn",
        "student.health.demo@vinuni.edu.vn",
        "student.liberal.demo@vinuni.edu.vn",
        "admin.global.demo@vinuni.edu.vn",
        "admin.business.demo@vinuni.edu.vn",
        "admin.cecs.demo@vinuni.edu.vn",
        "admin.health.demo@vinuni.edu.vn",
        "admin.liberal.demo@vinuni.edu.vn",
    } <= emails


def test_demo_seed_plan_has_academic_data_without_phase_5b_activity_data():
    plan = seed_demo_data.build_seed_plan()
    course_counts = Counter(course.institute_code for course in plan.courses)

    assert course_counts["VIB"] >= 6
    assert course_counts["CECS"] >= 6
    assert course_counts["CHS"] >= 5
    assert course_counts["CASE"] >= 5
    assert len(plan.enrollments) >= 50 * 3
    assert len(plan.schedules) == 50 * 5
    assert len(plan.deadlines) == 50 * 3
    assert all(schedule.end_time > schedule.start_time for schedule in plan.schedules)


def test_demo_seed_plan_uses_stable_ids_for_idempotency():
    first = seed_demo_data.build_seed_plan()
    second = seed_demo_data.build_seed_plan()

    assert [user.id for user in first.users] == [user.id for user in second.users]
    assert len({schedule.id for schedule in first.schedules}) == len(first.schedules)
    assert len({deadline.id for deadline in first.deadlines}) == len(first.deadlines)
    assert len({enrollment.id for enrollment in first.enrollments}) == len(first.enrollments)


def test_demo_seed_refuses_production():
    with pytest.raises(seed_demo_data.SeedError, match="production"):
        seed_demo_data.validate_seed_environment("production")


def test_demo_seed_requires_confirmation_before_connecting(monkeypatch):
    def fail_connect(_settings):
        raise AssertionError("seed without --yes must not connect")

    monkeypatch.setattr(seed_demo_data, "connect_direct", fail_connect)

    with pytest.raises(seed_demo_data.SeedError, match="--yes"):
        seed_demo_data.seed_demo_data(
            settings=type("Settings", (), {"app_env": "development"})(),
            yes=False,
        )


def test_demo_seed_summary_does_not_expose_password():
    plan = seed_demo_data.build_seed_plan()
    activity_plan = seed_demo_data.build_activity_seed_plan(plan)
    summary = "\n".join(
        [
            *seed_demo_data.seed_summary_lines(plan),
            *seed_demo_data.activity_seed_summary_lines(activity_plan),
        ]
    )

    assert seed_demo_data.DEMO_PASSWORD not in summary


def test_activity_seed_plan_has_expected_counts():
    activity_plan = seed_demo_data.build_activity_seed_plan()

    assert 10 <= len(activity_plan.notifications) <= 15
    assert 8 <= len(activity_plan.events) <= 12
    assert 20 <= len(activity_plan.tickets) <= 30
    assert activity_plan.notification_reads
    assert activity_plan.messages
    assert activity_plan.ticket_messages
    assert activity_plan.ticket_status_history
    assert activity_plan.question_events
    assert activity_plan.suggested_questions


def test_activity_seed_plan_required_demo_accounts_have_activity():
    academic_plan = seed_demo_data.build_seed_plan()
    activity_plan = seed_demo_data.build_activity_seed_plan(academic_plan)
    student_id_by_email = {
        profile.user_email: profile.student_id for profile in academic_plan.student_profiles
    }
    conversation_counts = Counter(
        conversation.user_email for conversation in activity_plan.conversations
    )
    tickets_by_student_id = {}
    for ticket in activity_plan.tickets:
        tickets_by_student_id.setdefault(ticket.student_id, []).append(ticket)

    for email in seed_demo_data.DEMO_STUDENT_EMAILS:
        student_id = student_id_by_email[email]
        statuses = {ticket.status for ticket in tickets_by_student_id[student_id]}

        assert 3 <= conversation_counts[email] <= 5
        assert statuses & {"submitted", "open"}
        assert "resolved" in statuses


def test_activity_seed_plan_trends_and_suggestions_cover_all_institutes():
    activity_plan = seed_demo_data.build_activity_seed_plan()
    trend_institutes = {
        trend.institute_code
        for trend in activity_plan.question_trends
        if trend.institute_code is not None
    }
    suggestion_institutes = {
        question.institute_code
        for question in activity_plan.suggested_questions
        if question.institute_code is not None
    }

    assert trend_institutes == seed_demo_data.REQUIRED_INSTITUTE_CODES
    assert seed_demo_data.REQUIRED_INSTITUTE_CODES <= suggestion_institutes


def test_activity_seed_plan_uses_stable_ids_for_idempotency():
    first = seed_demo_data.build_activity_seed_plan()
    second = seed_demo_data.build_activity_seed_plan()

    assert [item.id for item in first.notifications] == [
        item.id for item in second.notifications
    ]
    assert [item.id for item in first.conversations] == [
        item.id for item in second.conversations
    ]
    assert [item.id for item in first.tickets] == [item.id for item in second.tickets]
    assert len({item.id for item in first.messages}) == len(first.messages)
    assert len({item.id for item in first.suggested_questions}) == len(
        first.suggested_questions
    )


def test_activity_seed_plan_uses_schema_allowed_values():
    activity_plan = seed_demo_data.build_activity_seed_plan()

    assert {message.role for message in activity_plan.messages} <= {"user", "assistant"}
    assert {ticket.status for ticket in activity_plan.tickets} <= {
        "submitted",
        "open",
        "in_progress",
        "waiting_on_student",
        "resolved",
        "closed",
    }
    assert {question.source_type for question in activity_plan.suggested_questions} <= {
        "trend",
        "notification",
        "manual",
    }
