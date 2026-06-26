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
    summary = "\n".join(seed_demo_data.seed_summary_lines(plan))

    assert seed_demo_data.DEMO_PASSWORD not in summary
