from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from vinchatbot.app.services import academic as svc

TERM1 = {
    "term_id": uuid.UUID("aaaaaaaa-0000-0000-0000-000000000001"),
    "term_code": "2025-FALL",
    "term_name": "Fall Term 2025",
    "start_date": date(2025, 9, 1),
    "end_date": date(2025, 12, 20),
    "academic_year": 2025,
    "term_order": 1,
}
TERM2 = {
    "term_id": uuid.UUID("aaaaaaaa-0000-0000-0000-000000000002"),
    "term_code": "2026-SPRING",
    "term_name": "Spring Term 2026",
    "start_date": date(2026, 1, 12),
    "end_date": date(2026, 5, 15),
    "academic_year": 2026,
    "term_order": 2,
}


def _enrollment(course_code, credits, *, term, status, grade_4, passed, is_gpa_counted, earned):
    return {
        "id": uuid.uuid5(uuid.NAMESPACE_URL, f"enr:{course_code}:{term['term_code']}"),
        "student_id": uuid.UUID("11111111-1111-1111-1111-111111111111"),
        "course_id": uuid.uuid5(uuid.NAMESPACE_URL, f"course:{course_code}"),
        "course_code": course_code,
        "course_name": f"{course_code} course",
        "credits": credits,
        "course_level": 100,
        "department_code": course_code[:3],
        "is_general_education": False,
        "section_id": None,
        "section_code": None,
        "status": status,
        "attempt_no": 1,
        "is_improvement": False,
        "retake_of_enrollment_id": None,
        "grade_10": None,
        "grade_4": Decimal(str(grade_4)) if grade_4 is not None else None,
        "letter_grade": None,
        "passed": passed,
        "earned_credits": earned,
        "is_gpa_counted": is_gpa_counted,
        "completed_at": None,
        **term,
    }


def _sample_enrollments():
    return [
        # Term 1: 3.0*3 + 4.0*2 = 17 / 5 = 3.40 ; PE (0 credits) excluded from GPA.
        _enrollment("MATH101", 3, term=TERM1, status="completed", grade_4=3.0, passed=True,
                    is_gpa_counted=True, earned=3),
        _enrollment("GEN101", 2, term=TERM1, status="completed", grade_4=4.0, passed=True,
                    is_gpa_counted=True, earned=2),
        _enrollment("PE101", 0, term=TERM1, status="completed", grade_4=None, passed=True,
                    is_gpa_counted=False, earned=0),
        # Term 2: a failed 3-credit course — counts in CPA, grants no earned credits.
        _enrollment("CS201", 3, term=TERM2, status="failed", grade_4=0.0, passed=False,
                    is_gpa_counted=True, earned=0),
    ]


def test_term_gpa_is_credit_weighted_and_excludes_zero_credit():
    assert svc.compute_term_gpa(
        [e for e in _sample_enrollments() if e["term_code"] == "2025-FALL"]
    ) == Decimal("3.40")


def test_cumulative_cpa_includes_failed_course():
    # 17 points over 8 GPA credits (3+2+3) = 2.125 -> 2.13.
    assert svc.compute_cpa(_sample_enrollments()) == Decimal("2.13")


def test_earned_credits_only_counts_passed_courses():
    # MATH101 (3) + GEN101 (2) + PE101 (0); CS201 failed -> excluded.
    assert svc.compute_earned_credits(_sample_enrollments()) == 5


def test_failed_course_ids_detects_unpassed_failed_attempt():
    failed = svc.compute_failed_course_ids(_sample_enrollments())
    assert uuid.uuid5(uuid.NAMESPACE_URL, "course:CS201") in failed
    assert uuid.uuid5(uuid.NAMESPACE_URL, "course:MATH101") not in failed


def test_failed_course_not_reported_when_later_passed():
    enrollments = _sample_enrollments()
    # A later passing retake of CS201 clears it from the failed set.
    enrollments.append(
        _enrollment("CS201", 3, term=TERM2, status="completed", grade_4=2.5, passed=True,
                    is_gpa_counted=True, earned=3)
    )
    assert uuid.uuid5(uuid.NAMESPACE_URL, "course:CS201") not in svc.compute_failed_course_ids(
        enrollments
    )


def test_transcript_groups_by_term_with_running_cpa():
    transcript = svc.build_transcript(
        uuid.UUID("11111111-1111-1111-1111-111111111111"), _sample_enrollments()
    )
    assert [g.term.code for g in transcript.terms] == ["2025-FALL", "2026-SPRING"]
    assert transcript.terms[0].term_gpa == Decimal("3.40")
    assert transcript.terms[0].cumulative_cpa == Decimal("3.40")
    assert transcript.terms[1].term_gpa == Decimal("0.00")  # failed-only term
    assert transcript.terms[1].cumulative_cpa == Decimal("2.13")
    assert transcript.summary.earned_credits == 5


def test_month_window_uses_vinuni_local_time():
    start, end = svc.month_window(2026, 6)
    assert start.year == 2026 and start.month == 6 and start.day == 1
    assert end.month == 7
    assert start.utcoffset() is not None  # tz-aware (VinUni +07)
