from __future__ import annotations

import argparse
import base64
import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import psycopg

try:
    from scripts.db_migrate import MigrationError, connect_direct
except ModuleNotFoundError:  # pragma: no cover - used when executed as python scripts/seed_demo_data.py
    from db_migrate import MigrationError, connect_direct
from vinchatbot.app.core.config import Settings, get_settings

DEMO_PASSWORD = "Demo@123456"
DEMO_NAMESPACE = uuid.UUID("0c33c4dd-b75b-4e78-ae57-b4f7646f3c7b")
DEMO_ACADEMIC_YEAR = "2026-2027"
DEMO_SEMESTER = "Fall 2026"
ALLOWED_SEED_ENVS = {"development", "dev", "local", "test"}
REQUIRED_ROLE_CODES = {"student", "institute_admin", "global_admin", "staff"}
REQUIRED_INSTITUTE_CODES = {"VIB", "CECS", "CHS", "CASE"}


class SeedError(RuntimeError):
    """Safe seed error. Messages must never include database URLs or secrets."""


@dataclass(frozen=True)
class DemoUser:
    id: uuid.UUID
    email: str
    full_name: str
    preferred_name: str
    role_codes: tuple[str, ...]
    is_student: bool


@dataclass(frozen=True)
class DemoStudentProfile:
    id: uuid.UUID
    user_email: str
    student_id: str
    institute_code: str
    program: str
    major: str
    cohort: int
    academic_year: int
    preferred_language: str
    advisor_name: str
    advisor_email: str


@dataclass(frozen=True)
class DemoAcademicSummary:
    student_id: str
    gpa: Decimal
    credits_earned: int
    credits_required: int
    current_semester: str
    academic_status: str


@dataclass(frozen=True)
class DemoCourse:
    id: uuid.UUID
    institute_code: str
    course_code: str
    course_title: str
    credits: int
    semester: str
    academic_year: str
    instructor: str


@dataclass(frozen=True)
class DemoEnrollment:
    id: uuid.UUID
    student_id: str
    course_code: str
    semester: str
    academic_year: str
    status: str = "enrolled"


@dataclass(frozen=True)
class DemoSchedule:
    id: uuid.UUID
    student_id: str
    course_code: str | None
    semester: str | None
    academic_year: str | None
    title: str
    schedule_type: str
    start_time: datetime
    end_time: datetime
    location: str
    building: str
    room: str
    instructor: str | None
    recurrence_rule: str | None = None


@dataclass(frozen=True)
class DemoDeadline:
    id: uuid.UUID
    student_id: str
    course_code: str | None
    semester: str | None
    academic_year: str | None
    title: str
    kind: str
    due_at: datetime
    source_title: str
    source_url: str | None = None


@dataclass(frozen=True)
class DemoSeedPlan:
    users: tuple[DemoUser, ...]
    student_profiles: tuple[DemoStudentProfile, ...]
    academic_summaries: tuple[DemoAcademicSummary, ...]
    courses: tuple[DemoCourse, ...]
    enrollments: tuple[DemoEnrollment, ...]
    schedules: tuple[DemoSchedule, ...]
    deadlines: tuple[DemoDeadline, ...]

    @property
    def students(self) -> tuple[DemoUser, ...]:
        return tuple(user for user in self.users if user.is_student)

    @property
    def admins(self) -> tuple[DemoUser, ...]:
        return tuple(user for user in self.users if not user.is_student)

    def student_distribution(self) -> dict[str, int]:
        distribution = dict.fromkeys(REQUIRED_INSTITUTE_CODES, 0)
        for profile in self.student_profiles:
            distribution[profile.institute_code] += 1
        return distribution


@dataclass(frozen=True)
class StudentGroup:
    institute_code: str
    count: int
    email_prefix: str
    required_email: str
    program: str
    majors: tuple[str, ...]
    advisor_name: str
    advisor_email: str


def deterministic_uuid(label: str) -> uuid.UUID:
    return uuid.uuid5(DEMO_NAMESPACE, label)


def hash_password(password: str) -> str:
    iterations = 210_000
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    salt_b64 = base64.urlsafe_b64encode(salt).decode("ascii")
    digest_b64 = base64.urlsafe_b64encode(digest).decode("ascii")
    return f"pbkdf2_sha256${iterations}${salt_b64}${digest_b64}"


def validate_seed_environment(app_env: str) -> None:
    env = (app_env or "").strip().lower()
    if env == "production":
        raise SeedError("Refusing to seed demo data when APP_ENV=production.")
    if env not in ALLOWED_SEED_ENVS:
        allowed = ", ".join(sorted(ALLOWED_SEED_ENVS))
        raise SeedError(f"Refusing to seed demo data for APP_ENV={env!r}; allowed: {allowed}.")


def build_seed_plan() -> DemoSeedPlan:
    student_groups = (
        StudentGroup(
            institute_code="VIB",
            count=20,
            email_prefix="student.business",
            required_email="student.business.demo@vinuni.edu.vn",
            program="Bachelor of Business Administration",
            majors=("Finance", "Marketing", "Operations Management", "Hospitality Management"),
            advisor_name="Linh Tran",
            advisor_email="advisor.vib.demo@vinuni.edu.vn",
        ),
        StudentGroup(
            institute_code="CECS",
            count=15,
            email_prefix="student.cs",
            required_email="student.cs.demo@vinuni.edu.vn",
            program="Bachelor of Computer Science",
            majors=("Computer Science", "Data Science", "Electrical Engineering"),
            advisor_name="Minh Nguyen",
            advisor_email="advisor.cecs.demo@vinuni.edu.vn",
        ),
        StudentGroup(
            institute_code="CHS",
            count=10,
            email_prefix="student.health",
            required_email="student.health.demo@vinuni.edu.vn",
            program="Bachelor of Health Sciences",
            majors=("Nursing", "Biomedical Science", "Healthcare Management"),
            advisor_name="Hanh Pham",
            advisor_email="advisor.chs.demo@vinuni.edu.vn",
        ),
        StudentGroup(
            institute_code="CASE",
            count=5,
            email_prefix="student.liberal",
            required_email="student.liberal.demo@vinuni.edu.vn",
            program="Bachelor of Liberal Arts",
            majors=("Communication", "Psychology", "Education Studies"),
            advisor_name="An Le",
            advisor_email="advisor.case.demo@vinuni.edu.vn",
        ),
    )

    users: list[DemoUser] = []
    profiles: list[DemoStudentProfile] = []
    summaries: list[DemoAcademicSummary] = []
    global_student_index = 0

    for group in student_groups:
        for group_index in range(1, group.count + 1):
            global_student_index += 1
            email = (
                group.required_email
                if group_index == 1
                else f"{group.email_prefix}{group_index:02d}.demo@vinuni.edu.vn"
            )
            preferred_name = f"{group.institute_code} Student {group_index:02d}"
            full_name = f"Demo {preferred_name}"
            student_id = f"D2026{group.institute_code}{group_index:03d}"
            academic_year = 1 + ((global_student_index - 1) % 4)
            gpa = Decimal("2.70") + Decimal((global_student_index * 7) % 120) / Decimal("100")

            users.append(
                DemoUser(
                    id=deterministic_uuid(f"user:{email}"),
                    email=email,
                    full_name=full_name,
                    preferred_name=preferred_name,
                    role_codes=("student",),
                    is_student=True,
                )
            )
            profiles.append(
                DemoStudentProfile(
                    id=deterministic_uuid(f"student-profile:{student_id}"),
                    user_email=email,
                    student_id=student_id,
                    institute_code=group.institute_code,
                    program=group.program,
                    major=group.majors[(group_index - 1) % len(group.majors)],
                    cohort=2026 - ((group_index - 1) % 4),
                    academic_year=academic_year,
                    preferred_language="vi" if group_index % 2 else "en",
                    advisor_name=group.advisor_name,
                    advisor_email=group.advisor_email,
                )
            )
            summaries.append(
                DemoAcademicSummary(
                    student_id=student_id,
                    gpa=gpa.quantize(Decimal("0.01")),
                    credits_earned=18 + (academic_year - 1) * 28 + (group_index % 5) * 3,
                    credits_required=120,
                    current_semester=DEMO_SEMESTER,
                    academic_status="normal",
                )
            )

    users.extend(
        (
            DemoUser(
                id=deterministic_uuid("user:admin.global.demo@vinuni.edu.vn"),
                email="admin.global.demo@vinuni.edu.vn",
                full_name="Demo Global Admin",
                preferred_name="Global Admin",
                role_codes=("global_admin",),
                is_student=False,
            ),
            DemoUser(
                id=deterministic_uuid("user:admin.business.demo@vinuni.edu.vn"),
                email="admin.business.demo@vinuni.edu.vn",
                full_name="Demo Business Admin",
                preferred_name="Business Admin",
                role_codes=("institute_admin", "staff"),
                is_student=False,
            ),
            DemoUser(
                id=deterministic_uuid("user:admin.cecs.demo@vinuni.edu.vn"),
                email="admin.cecs.demo@vinuni.edu.vn",
                full_name="Demo CECS Admin",
                preferred_name="CECS Admin",
                role_codes=("institute_admin", "staff"),
                is_student=False,
            ),
            DemoUser(
                id=deterministic_uuid("user:admin.health.demo@vinuni.edu.vn"),
                email="admin.health.demo@vinuni.edu.vn",
                full_name="Demo Health Admin",
                preferred_name="Health Admin",
                role_codes=("institute_admin", "staff"),
                is_student=False,
            ),
            DemoUser(
                id=deterministic_uuid("user:admin.liberal.demo@vinuni.edu.vn"),
                email="admin.liberal.demo@vinuni.edu.vn",
                full_name="Demo Liberal Arts Admin",
                preferred_name="Liberal Arts Admin",
                role_codes=("institute_admin", "staff"),
                is_student=False,
            ),
        )
    )

    courses = build_courses()
    enrollments = build_enrollments(profiles, courses)
    schedules = build_schedules(profiles, courses, enrollments)
    deadlines = build_deadlines(profiles, courses, enrollments)

    return DemoSeedPlan(
        users=tuple(users),
        student_profiles=tuple(profiles),
        academic_summaries=tuple(summaries),
        courses=tuple(courses),
        enrollments=tuple(enrollments),
        schedules=tuple(schedules),
        deadlines=tuple(deadlines),
    )


def build_courses() -> list[DemoCourse]:
    course_rows = (
        ("VIB", "BUS101", "Principles of Management", 3, "Nguyen Hoang"),
        ("VIB", "BUS120", "Financial Accounting", 3, "Mai Anh"),
        ("VIB", "BUS201", "Marketing Management", 3, "Tran Quang"),
        ("VIB", "BUS230", "Business Analytics", 3, "Linh Pham"),
        ("VIB", "BUS250", "Organizational Behavior", 3, "Hoa Do"),
        ("VIB", "BUS310", "Entrepreneurship", 3, "Minh Dang"),
        ("CECS", "CSC101", "Programming Fundamentals", 3, "Khoa Le"),
        ("CECS", "CSC202", "Data Structures and Algorithms", 3, "Tuan Nguyen"),
        ("CECS", "CSC250", "Database Systems", 3, "Trang Bui"),
        ("CECS", "CSC310", "Artificial Intelligence", 3, "Son Pham"),
        ("CECS", "ECE210", "Digital Systems", 3, "Duc Tran"),
        ("CECS", "CSC330", "Software Engineering", 3, "Hieu Vo"),
        ("CHS", "HSC101", "Biomedical Science Foundations", 3, "Lan Nguyen"),
        ("CHS", "MED210", "Human Anatomy", 4, "Thao Pham"),
        ("CHS", "NUR220", "Health Communication", 3, "My Le"),
        ("CHS", "HSC230", "Epidemiology", 3, "Binh Tran"),
        ("CHS", "HSC310", "Clinical Skills", 4, "Ha Nguyen"),
        ("CASE", "LIB101", "Critical Thinking", 3, "Vy Tran"),
        ("CASE", "ENG120", "Academic Writing", 3, "Quan Le"),
        ("CASE", "VIE210", "Vietnamese Culture and Society", 3, "Huong Do"),
        ("CASE", "EDU220", "Learning Sciences", 3, "Nam Pham"),
        ("CASE", "ART230", "Visual Communication", 3, "Mai Tran"),
    )
    return [
        DemoCourse(
            id=deterministic_uuid(f"course:{course_code}:{DEMO_SEMESTER}:{DEMO_ACADEMIC_YEAR}"),
            institute_code=institute_code,
            course_code=course_code,
            course_title=course_title,
            credits=credits,
            semester=DEMO_SEMESTER,
            academic_year=DEMO_ACADEMIC_YEAR,
            instructor=instructor,
        )
        for institute_code, course_code, course_title, credits, instructor in course_rows
    ]


def build_enrollments(
    profiles: list[DemoStudentProfile],
    courses: list[DemoCourse],
) -> list[DemoEnrollment]:
    courses_by_institute = group_courses_by_institute(courses)
    enrollments: list[DemoEnrollment] = []
    for student_index, profile in enumerate(profiles):
        institute_courses = courses_by_institute[profile.institute_code]
        course_count = 3 + (student_index % 3)
        start_index = student_index % len(institute_courses)
        selected_courses = [
            institute_courses[(start_index + offset) % len(institute_courses)]
            for offset in range(course_count)
        ]
        for course in selected_courses:
            enrollments.append(
                DemoEnrollment(
                    id=deterministic_uuid(f"enrollment:{profile.student_id}:{course.course_code}"),
                    student_id=profile.student_id,
                    course_code=course.course_code,
                    semester=course.semester,
                    academic_year=course.academic_year,
                )
            )
    return enrollments


def build_schedules(
    profiles: list[DemoStudentProfile],
    courses: list[DemoCourse],
    enrollments: list[DemoEnrollment],
) -> list[DemoSchedule]:
    course_lookup = course_lookup_by_key(courses)
    enrollments_by_student = group_enrollments_by_student(enrollments)
    base_date = datetime(2026, 9, 7, tzinfo=UTC)
    schedules: list[DemoSchedule] = []

    for student_index, profile in enumerate(profiles):
        student_enrollments = enrollments_by_student[profile.student_id]
        week_offset = student_index % 4
        for slot, enrollment in enumerate(student_enrollments[:3]):
            course = course_lookup[(enrollment.course_code, enrollment.semester, enrollment.academic_year)]
            day_offset = slot * 2
            start_hour = 9 + slot * 2
            start_time = base_date + timedelta(days=day_offset, weeks=week_offset, hours=start_hour)
            schedule_type = "lab" if slot == 1 else "class"
            schedules.append(
                DemoSchedule(
                    id=deterministic_uuid(
                        f"schedule:{profile.student_id}:{course.course_code}:{schedule_type}"
                    ),
                    student_id=profile.student_id,
                    course_code=course.course_code,
                    semester=course.semester,
                    academic_year=course.academic_year,
                    title=f"{course.course_code} {course.course_title}",
                    schedule_type=schedule_type,
                    start_time=start_time,
                    end_time=start_time + timedelta(minutes=90),
                    location="VinUni Campus",
                    building=f"Building {slot + 1}",
                    room=f"{slot + 1}0{(student_index % 5) + 1}",
                    instructor=course.instructor,
                    recurrence_rule="FREQ=WEEKLY;COUNT=12",
                )
            )

        exam_course = course_lookup[
            (
                student_enrollments[0].course_code,
                student_enrollments[0].semester,
                student_enrollments[0].academic_year,
            )
        ]
        exam_start = datetime(2026, 12, 10, 8, 30, tzinfo=UTC) + timedelta(
            days=student_index % 6
        )
        schedules.append(
            DemoSchedule(
                id=deterministic_uuid(f"schedule:{profile.student_id}:{exam_course.course_code}:exam"),
                student_id=profile.student_id,
                course_code=exam_course.course_code,
                semester=exam_course.semester,
                academic_year=exam_course.academic_year,
                title=f"{exam_course.course_code} Midterm Exam",
                schedule_type="exam",
                start_time=exam_start,
                end_time=exam_start + timedelta(hours=2),
                location="VinUni Campus",
                building="Examination Hall",
                room=f"E{(student_index % 4) + 1}",
                instructor=exam_course.instructor,
            )
        )

        advising_start = datetime(2026, 9, 18, 7, 30, tzinfo=UTC) + timedelta(
            days=student_index % 10
        )
        schedules.append(
            DemoSchedule(
                id=deterministic_uuid(f"schedule:{profile.student_id}:advising"),
                student_id=profile.student_id,
                course_code=None,
                semester=None,
                academic_year=None,
                title="Academic Advising Meeting",
                schedule_type="meeting",
                start_time=advising_start,
                end_time=advising_start + timedelta(minutes=45),
                location="VinUni Campus",
                building="Student Success Center",
                room=f"ADV{(student_index % 8) + 1}",
                instructor=profile.advisor_name,
            )
        )

    return schedules


def build_deadlines(
    profiles: list[DemoStudentProfile],
    courses: list[DemoCourse],
    enrollments: list[DemoEnrollment],
) -> list[DemoDeadline]:
    course_lookup = course_lookup_by_key(courses)
    enrollments_by_student = group_enrollments_by_student(enrollments)
    deadlines: list[DemoDeadline] = []

    for student_index, profile in enumerate(profiles):
        student_enrollments = enrollments_by_student[profile.student_id]
        for offset, enrollment in enumerate(student_enrollments[:2]):
            course = course_lookup[(enrollment.course_code, enrollment.semester, enrollment.academic_year)]
            due_at = datetime(2026, 10, 6 + offset * 14, 16, 0, tzinfo=UTC) + timedelta(
                days=student_index % 5
            )
            deadlines.append(
                DemoDeadline(
                    id=deterministic_uuid(
                        f"deadline:{profile.student_id}:{course.course_code}:assignment-{offset + 1}"
                    ),
                    student_id=profile.student_id,
                    course_code=course.course_code,
                    semester=course.semester,
                    academic_year=course.academic_year,
                    title=f"{course.course_code} Assignment {offset + 1}",
                    kind="assignment",
                    due_at=due_at,
                    source_title="Phase 5A demo academic seed",
                )
            )

        registration_due = datetime(2026, 9, 30, 16, 0, tzinfo=UTC) + timedelta(
            days=student_index % 3
        )
        deadlines.append(
            DemoDeadline(
                id=deterministic_uuid(f"deadline:{profile.student_id}:registration-check"),
                student_id=profile.student_id,
                course_code=None,
                semester=None,
                academic_year=None,
                title="Semester Registration Check",
                kind="registration",
                due_at=registration_due,
                source_title="Phase 5A demo academic seed",
            )
        )

    return deadlines


def group_courses_by_institute(courses: list[DemoCourse]) -> dict[str, list[DemoCourse]]:
    grouped: dict[str, list[DemoCourse]] = {}
    for course in courses:
        grouped.setdefault(course.institute_code, []).append(course)
    return grouped


def course_lookup_by_key(
    courses: list[DemoCourse],
) -> dict[tuple[str, str, str], DemoCourse]:
    return {
        (course.course_code, course.semester, course.academic_year): course
        for course in courses
    }


def group_enrollments_by_student(
    enrollments: list[DemoEnrollment],
) -> dict[str, list[DemoEnrollment]]:
    grouped: dict[str, list[DemoEnrollment]] = {}
    for enrollment in enrollments:
        grouped.setdefault(enrollment.student_id, []).append(enrollment)
    return grouped


def seed_summary_lines(plan: DemoSeedPlan) -> list[str]:
    distribution = ", ".join(
        f"{code}: {count}" for code, count in sorted(plan.student_distribution().items())
    )
    return [
        "Phase 5A demo academic seed plan:",
        f"  users: {len(plan.users)} total ({len(plan.students)} students, {len(plan.admins)} admins/staff)",
        f"  student distribution: {distribution}",
        f"  courses: {len(plan.courses)}",
        f"  enrollments: {len(plan.enrollments)}",
        f"  schedules: {len(plan.schedules)}",
        f"  deadlines: {len(plan.deadlines)}",
    ]


def seed_demo_data(
    settings: Settings | None = None,
    *,
    section: str = "academic",
    yes: bool = False,
) -> DemoSeedPlan:
    if section != "academic":
        raise SeedError(f"Unsupported seed section {section!r}.")
    settings = settings or get_settings()
    validate_seed_environment(settings.app_env)
    if not yes:
        raise SeedError("Demo seed requires --yes.")

    plan = build_seed_plan()
    with connect_direct(settings) as conn:
        with conn.transaction():
            seed_academic_plan(conn, plan)
    return plan


def seed_academic_plan(conn: psycopg.Connection[Any], plan: DemoSeedPlan) -> None:
    role_ids = fetch_required_ids(conn, "roles", "code", REQUIRED_ROLE_CODES)
    institute_ids = fetch_required_ids(conn, "institutes", "code", REQUIRED_INSTITUTE_CODES)
    upsert_users(conn, plan.users)
    user_ids = fetch_required_ids(conn, "users", "email", {user.email for user in plan.users})
    upsert_user_roles(conn, plan.users, user_ids, role_ids)
    upsert_courses(conn, plan.courses, institute_ids)
    course_ids = fetch_course_ids(conn, plan.courses)
    upsert_student_profiles(conn, plan.student_profiles, user_ids, institute_ids)
    profile_ids = fetch_required_ids(
        conn,
        "student_profiles",
        "student_id",
        {profile.student_id for profile in plan.student_profiles},
    )
    upsert_academic_summaries(conn, plan.academic_summaries, profile_ids)
    upsert_enrollments(conn, plan.enrollments, profile_ids, course_ids)
    upsert_schedules(conn, plan.schedules, profile_ids, course_ids)
    upsert_deadlines(conn, plan.deadlines, profile_ids, course_ids)


def fetch_required_ids(
    conn: psycopg.Connection[Any],
    table: str,
    key_column: str,
    required_values: set[str],
) -> dict[str, uuid.UUID]:
    rows = conn.execute(
        f"select id, {key_column} from {table} where {key_column} = any(%s)",
        (list(required_values),),
    ).fetchall()
    ids = {str(row[key_column]): row["id"] for row in rows}
    missing = sorted(required_values - set(ids))
    if missing:
        raise SeedError(
            f"Required base data missing from {table}: {', '.join(missing)}. "
            "Run python scripts/db_migrate.py first."
        )
    return ids


def fetch_course_ids(
    conn: psycopg.Connection[Any],
    courses: tuple[DemoCourse, ...],
) -> dict[tuple[str, str, str], uuid.UUID]:
    rows = conn.execute(
        """
        select id, course_code, semester, academic_year
        from courses
        where course_code = any(%s)
          and semester = any(%s)
          and academic_year = any(%s)
        """,
        (
            list({course.course_code for course in courses}),
            list({course.semester for course in courses}),
            list({course.academic_year for course in courses}),
        ),
    ).fetchall()
    ids = {
        (row["course_code"], row["semester"], row["academic_year"]): row["id"]
        for row in rows
    }
    expected = {
        (course.course_code, course.semester, course.academic_year) for course in courses
    }
    missing = sorted(expected - set(ids))
    if missing:
        raise SeedError("Required demo courses were not inserted.")
    return ids


def upsert_users(conn: psycopg.Connection[Any], users: tuple[DemoUser, ...]) -> None:
    for user in users:
        conn.execute(
            """
            insert into users (
                id, email, password_hash, full_name, preferred_name, status
            )
            values (%s, %s, %s, %s, %s, 'active')
            on conflict (email) do update
            set
                full_name = excluded.full_name,
                preferred_name = excluded.preferred_name,
                status = 'active',
                password_hash = coalesce(users.password_hash, excluded.password_hash),
                updated_at = now()
            """,
            (
                user.id,
                user.email,
                hash_password(DEMO_PASSWORD),
                user.full_name,
                user.preferred_name,
            ),
        )


def upsert_user_roles(
    conn: psycopg.Connection[Any],
    users: tuple[DemoUser, ...],
    user_ids: dict[str, uuid.UUID],
    role_ids: dict[str, uuid.UUID],
) -> None:
    for user in users:
        for role_code in user.role_codes:
            conn.execute(
                """
                insert into user_roles (user_id, role_id)
                values (%s, %s)
                on conflict (user_id, role_id) do nothing
                """,
                (user_ids[user.email], role_ids[role_code]),
            )


def upsert_courses(
    conn: psycopg.Connection[Any],
    courses: tuple[DemoCourse, ...],
    institute_ids: dict[str, uuid.UUID],
) -> None:
    for course in courses:
        conn.execute(
            """
            insert into courses (
                id, institute_id, course_code, course_title, credits,
                semester, academic_year, instructor, is_active
            )
            values (%s, %s, %s, %s, %s, %s, %s, %s, true)
            on conflict (course_code, semester, academic_year) do update
            set
                institute_id = excluded.institute_id,
                course_title = excluded.course_title,
                credits = excluded.credits,
                instructor = excluded.instructor,
                is_active = true
            """,
            (
                course.id,
                institute_ids[course.institute_code],
                course.course_code,
                course.course_title,
                course.credits,
                course.semester,
                course.academic_year,
                course.instructor,
            ),
        )


def upsert_student_profiles(
    conn: psycopg.Connection[Any],
    profiles: tuple[DemoStudentProfile, ...],
    user_ids: dict[str, uuid.UUID],
    institute_ids: dict[str, uuid.UUID],
) -> None:
    for profile in profiles:
        conn.execute(
            """
            insert into student_profiles (
                id, user_id, student_id, institute_id, program, major, cohort,
                academic_year, student_status, preferred_language, advisor_name,
                advisor_email, ai_personalization_enabled
            )
            values (%s, %s, %s, %s, %s, %s, %s, %s, 'active', %s, %s, %s, true)
            on conflict (user_id) do update
            set
                student_id = excluded.student_id,
                institute_id = excluded.institute_id,
                program = excluded.program,
                major = excluded.major,
                cohort = excluded.cohort,
                academic_year = excluded.academic_year,
                student_status = 'active',
                preferred_language = excluded.preferred_language,
                advisor_name = excluded.advisor_name,
                advisor_email = excluded.advisor_email,
                ai_personalization_enabled = true,
                updated_at = now()
            """,
            (
                profile.id,
                user_ids[profile.user_email],
                profile.student_id,
                institute_ids[profile.institute_code],
                profile.program,
                profile.major,
                profile.cohort,
                profile.academic_year,
                profile.preferred_language,
                profile.advisor_name,
                profile.advisor_email,
            ),
        )


def upsert_academic_summaries(
    conn: psycopg.Connection[Any],
    summaries: tuple[DemoAcademicSummary, ...],
    profile_ids: dict[str, uuid.UUID],
) -> None:
    for summary in summaries:
        conn.execute(
            """
            insert into academic_summaries (
                id, student_profile_id, gpa, credits_earned, credits_required,
                current_semester, academic_status, updated_at
            )
            values (%s, %s, %s, %s, %s, %s, %s, now())
            on conflict (student_profile_id) do update
            set
                gpa = excluded.gpa,
                credits_earned = excluded.credits_earned,
                credits_required = excluded.credits_required,
                current_semester = excluded.current_semester,
                academic_status = excluded.academic_status,
                updated_at = now()
            """,
            (
                deterministic_uuid(f"academic-summary:{summary.student_id}"),
                profile_ids[summary.student_id],
                summary.gpa,
                summary.credits_earned,
                summary.credits_required,
                summary.current_semester,
                summary.academic_status,
            ),
        )


def upsert_enrollments(
    conn: psycopg.Connection[Any],
    enrollments: tuple[DemoEnrollment, ...],
    profile_ids: dict[str, uuid.UUID],
    course_ids: dict[tuple[str, str, str], uuid.UUID],
) -> None:
    for enrollment in enrollments:
        course_key = (enrollment.course_code, enrollment.semester, enrollment.academic_year)
        conn.execute(
            """
            insert into enrollments (id, student_profile_id, course_id, status)
            values (%s, %s, %s, %s)
            on conflict (student_profile_id, course_id) do update
            set status = excluded.status
            """,
            (
                enrollment.id,
                profile_ids[enrollment.student_id],
                course_ids[course_key],
                enrollment.status,
            ),
        )


def upsert_schedules(
    conn: psycopg.Connection[Any],
    schedules: tuple[DemoSchedule, ...],
    profile_ids: dict[str, uuid.UUID],
    course_ids: dict[tuple[str, str, str], uuid.UUID],
) -> None:
    for schedule in schedules:
        course_id = None
        if schedule.course_code and schedule.semester and schedule.academic_year:
            course_id = course_ids[
                (schedule.course_code, schedule.semester, schedule.academic_year)
            ]
        conn.execute(
            """
            insert into schedules (
                id, student_profile_id, course_id, title, schedule_type,
                start_time, end_time, location, building, room, instructor,
                recurrence_rule
            )
            values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            on conflict (id) do update
            set
                student_profile_id = excluded.student_profile_id,
                course_id = excluded.course_id,
                title = excluded.title,
                schedule_type = excluded.schedule_type,
                start_time = excluded.start_time,
                end_time = excluded.end_time,
                location = excluded.location,
                building = excluded.building,
                room = excluded.room,
                instructor = excluded.instructor,
                recurrence_rule = excluded.recurrence_rule
            """,
            (
                schedule.id,
                profile_ids[schedule.student_id],
                course_id,
                schedule.title,
                schedule.schedule_type,
                schedule.start_time,
                schedule.end_time,
                schedule.location,
                schedule.building,
                schedule.room,
                schedule.instructor,
                schedule.recurrence_rule,
            ),
        )


def upsert_deadlines(
    conn: psycopg.Connection[Any],
    deadlines: tuple[DemoDeadline, ...],
    profile_ids: dict[str, uuid.UUID],
    course_ids: dict[tuple[str, str, str], uuid.UUID],
) -> None:
    for deadline in deadlines:
        course_id = None
        if deadline.course_code and deadline.semester and deadline.academic_year:
            course_id = course_ids[
                (deadline.course_code, deadline.semester, deadline.academic_year)
            ]
        conn.execute(
            """
            insert into deadlines (
                id, student_profile_id, course_id, title, kind, due_at,
                source_title, source_url
            )
            values (%s, %s, %s, %s, %s, %s, %s, %s)
            on conflict (id) do update
            set
                student_profile_id = excluded.student_profile_id,
                course_id = excluded.course_id,
                title = excluded.title,
                kind = excluded.kind,
                due_at = excluded.due_at,
                source_title = excluded.source_title,
                source_url = excluded.source_url
            """,
            (
                deadline.id,
                profile_ids[deadline.student_id],
                course_id,
                deadline.title,
                deadline.kind,
                deadline.due_at,
                deadline.source_title,
                deadline.source_url,
            ),
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed Phase 5A demo academic data.")
    parser.add_argument(
        "--section",
        choices=["academic"],
        default="academic",
        help="Demo seed section to apply.",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Confirm insertion/update of development demo data.",
    )
    args = parser.parse_args()

    if not args.yes:
        print("Demo seed would insert/update development demo data. Re-run with --yes to proceed.")
        return 1

    try:
        plan = build_seed_plan()
        for line in seed_summary_lines(plan):
            print(line)
        seed_demo_data(section=args.section, yes=args.yes)
    except (MigrationError, SeedError) as exc:
        print(f"Demo seed failed: {exc}")
        return 1
    except psycopg.Error as exc:
        print(f"Demo seed failed: database error {type(exc).__name__}")
        return 1

    print("Demo academic data seed complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
