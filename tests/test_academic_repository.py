from __future__ import annotations

from decimal import Decimal

from vinchatbot.app.repositories.academic import (
    enrollment_counts_for_gpa,
    is_failing_grade,
    requisite_is_satisfied,
)


def test_is_failing_grade_uses_10_point_and_4_point_thresholds():
    assert is_failing_grade(Decimal("3.99"), Decimal("2.0"))
    assert is_failing_grade(Decimal("7.0"), Decimal("0.99"))
    assert not is_failing_grade(Decimal("4.0"), Decimal("1.0"))
    assert not is_failing_grade(None, None)


def test_zero_credit_enrollments_do_not_count_for_gpa():
    assert not enrollment_counts_for_gpa(
        credits=0,
        status="completed",
        is_gpa_counted=True,
    )
    assert enrollment_counts_for_gpa(
        credits=3,
        status="completed",
        is_gpa_counted=True,
    )
    assert not enrollment_counts_for_gpa(
        credits=3,
        status="enrolled",
        is_gpa_counted=True,
    )


def test_requisite_satisfaction_rules_distinguish_prerequisite_and_corequisite():
    assert requisite_is_satisfied(
        requisite_type="prerequisite",
        required_passed=True,
        required_same_term=False,
    )
    assert not requisite_is_satisfied(
        requisite_type="prerequisite",
        required_passed=False,
        required_same_term=True,
    )
    assert requisite_is_satisfied(
        requisite_type="corequisite",
        required_passed=False,
        required_same_term=True,
    )
