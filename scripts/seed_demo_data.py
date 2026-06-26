from __future__ import annotations

import argparse
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
from vinchatbot.app.security.passwords import hash_password

DEMO_PASSWORD = "Demo@123456"
DEMO_NAMESPACE = uuid.UUID("0c33c4dd-b75b-4e78-ae57-b4f7646f3c7b")
DEMO_ACADEMIC_YEAR = "2026-2027"
DEMO_SEMESTER = "Fall 2026"
DEMO_ACTIVITY_START = datetime(2026, 10, 1, tzinfo=UTC)
DEMO_ACTIVITY_VISIBLE_FROM_DAYS_AGO = 14
DEMO_ACTIVITY_VISIBLE_UNTIL_DAYS = 90
ALLOWED_SEED_ENVS = {"development", "dev", "local", "test"}
REQUIRED_ROLE_CODES = {"student", "institute_admin", "global_admin", "staff"}
REQUIRED_INSTITUTE_CODES = {"VIB", "CECS", "CHS", "CASE"}
DEMO_STUDENT_EMAILS = (
    "student.business.demo@vinuni.edu.vn",
    "student.cs.demo@vinuni.edu.vn",
    "student.health.demo@vinuni.edu.vn",
    "student.liberal.demo@vinuni.edu.vn",
)
DEMO_ADMIN_EMAIL_BY_INSTITUTE = {
    "VIB": "admin.business.demo@vinuni.edu.vn",
    "CECS": "admin.cecs.demo@vinuni.edu.vn",
    "CHS": "admin.health.demo@vinuni.edu.vn",
    "CASE": "admin.liberal.demo@vinuni.edu.vn",
}


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
class DemoNotification:
    id: uuid.UUID
    notification_type: str
    title: str
    message: str
    priority: str
    status: str
    target_scope: str
    institute_code: str | None
    course_code: str | None
    semester: str | None
    academic_year: str | None
    cohort: int | None
    deadline: datetime | None
    event_date: datetime | None
    start_date: datetime | None
    end_date: datetime | None
    source_title: str
    source_url: str | None
    created_by_email: str | None
    category: str


@dataclass(frozen=True)
class DemoNotificationRead:
    id: uuid.UUID
    notification_id: uuid.UUID
    user_email: str
    read_at: datetime
    important: bool
    archived: bool = False


@dataclass(frozen=True)
class DemoEvent:
    id: uuid.UUID
    title: str
    description: str
    event_type: str
    location: str
    start_time: datetime
    end_time: datetime
    institute_code: str | None
    target_scope: str
    registration_required: bool
    registration_deadline: datetime | None


@dataclass(frozen=True)
class DemoConversation:
    id: uuid.UUID
    user_email: str
    title: str
    topic: str
    created_at: datetime
    updated_at: datetime
    last_message_at: datetime


@dataclass(frozen=True)
class DemoMessage:
    id: uuid.UUID
    conversation_id: uuid.UUID
    role: str
    content: str
    intent: str
    topic: str
    confidence: Decimal | None
    needs_human_review: bool
    created_at: datetime


@dataclass(frozen=True)
class DemoTicket:
    id: uuid.UUID
    student_id: str
    institute_code: str
    subject: str
    body: str
    department: str
    category: str
    priority: str
    status: str
    source_conversation_id: uuid.UUID | None
    origin_question: str | None
    assigned_admin_email: str | None
    submitted_at: datetime | None
    due_at: datetime | None
    sla_hours: int | None
    resolution: str | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class DemoTicketMessage:
    id: uuid.UUID
    ticket_id: uuid.UUID
    sender_email: str | None
    author_type: str
    body: str
    created_at: datetime


@dataclass(frozen=True)
class DemoTicketStatusHistory:
    id: uuid.UUID
    ticket_id: uuid.UUID
    old_status: str | None
    new_status: str
    changed_by_email: str | None
    changed_at: datetime


@dataclass(frozen=True)
class DemoQuestionEvent:
    id: uuid.UUID
    user_email: str | None
    conversation_id: uuid.UUID | None
    raw_question: str
    normalized_question: str
    intent: str
    topic: str
    institute_code: str | None
    course_code: str | None
    semester: str | None
    academic_year: str | None
    created_at: datetime
    is_anonymized: bool = True


@dataclass(frozen=True)
class DemoQuestionTrend:
    id: uuid.UUID
    topic: str
    intent: str
    institute_code: str | None
    course_code: str | None
    semester: str | None
    academic_year: str | None
    time_window: str
    frequency_count: int
    trend_score: Decimal
    last_seen_at: datetime


@dataclass(frozen=True)
class DemoSuggestedQuestion:
    id: uuid.UUID
    question_text: str
    source_type: str
    source_id: uuid.UUID | None
    notification_id: uuid.UUID | None
    topic: str
    intent: str
    category: str
    trigger_phase: str
    institute_code: str | None
    course_code: str | None
    semester: str | None
    academic_year: str | None
    cohort: int | None
    score: Decimal
    priority: int
    created_by_ai: bool
    approved_by_admin: bool
    is_active: bool
    valid_from: datetime
    valid_until: datetime


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
class DemoActivitySeedPlan:
    notifications: tuple[DemoNotification, ...]
    notification_reads: tuple[DemoNotificationRead, ...]
    events: tuple[DemoEvent, ...]
    conversations: tuple[DemoConversation, ...]
    messages: tuple[DemoMessage, ...]
    tickets: tuple[DemoTicket, ...]
    ticket_messages: tuple[DemoTicketMessage, ...]
    ticket_status_history: tuple[DemoTicketStatusHistory, ...]
    question_events: tuple[DemoQuestionEvent, ...]
    question_trends: tuple[DemoQuestionTrend, ...]
    suggested_questions: tuple[DemoSuggestedQuestion, ...]


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


def seed_runtime_now() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


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


def build_activity_seed_plan(
    academic_plan: DemoSeedPlan | None = None,
    *,
    seed_now: datetime | None = None,
) -> DemoActivitySeedPlan:
    academic_plan = academic_plan or build_seed_plan()
    seed_now = seed_now or seed_runtime_now()
    course_lookup = course_lookup_by_key(list(academic_plan.courses))
    courses_by_institute = group_courses_by_institute(list(academic_plan.courses))
    enrollments_by_student = group_enrollments_by_student(list(academic_plan.enrollments))
    profiles_by_email = {profile.user_email: profile for profile in academic_plan.student_profiles}

    notifications = build_activity_notifications(courses_by_institute, seed_now=seed_now)
    notification_reads = build_notification_reads(notifications, academic_plan)
    events = build_activity_events()
    conversations, messages = build_conversations_and_messages(
        academic_plan,
        course_lookup,
        enrollments_by_student,
    )
    tickets, ticket_messages, ticket_status_history = build_activity_tickets(
        academic_plan,
        conversations,
    )
    question_events = build_question_events(
        conversations,
        messages,
        profiles_by_email,
        course_lookup,
        enrollments_by_student,
    )
    question_trends = build_question_trends(courses_by_institute)
    suggested_questions = build_suggested_questions(
        notifications,
        events,
        tickets,
        question_trends,
        courses_by_institute,
        seed_now=seed_now,
    )

    return DemoActivitySeedPlan(
        notifications=tuple(notifications),
        notification_reads=tuple(notification_reads),
        events=tuple(events),
        conversations=tuple(conversations),
        messages=tuple(messages),
        tickets=tuple(tickets),
        ticket_messages=tuple(ticket_messages),
        ticket_status_history=tuple(ticket_status_history),
        question_events=tuple(question_events),
        question_trends=tuple(question_trends),
        suggested_questions=tuple(suggested_questions),
    )


def build_activity_notifications(
    courses_by_institute: dict[str, list[DemoCourse]],
    *,
    seed_now: datetime,
) -> list[DemoNotification]:
    bus230 = next(course for course in courses_by_institute["VIB"] if course.course_code == "BUS230")
    csc330 = next(course for course in courses_by_institute["CECS"] if course.course_code == "CSC330")
    visible_from = seed_now - timedelta(days=DEMO_ACTIVITY_VISIBLE_FROM_DAYS_AGO)
    visible_until = seed_now + timedelta(days=DEMO_ACTIVITY_VISIBLE_UNTIL_DAYS)
    rows = (
        (
            "final-exam-schedule",
            "academic",
            "exam",
            "Final exam schedule released",
            "Final exam windows for Fall 2026 are now available in the student portal.",
            "high",
            "all",
            None,
            None,
            None,
            None,
            None,
            DEMO_ACTIVITY_START + timedelta(days=72),
            visible_from,
            visible_until,
            "Exam Office demo notice",
        ),
        (
            "course-registration",
            "deadline",
            "course_registration",
            "Course registration closes soon",
            "Review your study plan and confirm Fall 2026 registration before the deadline.",
            "urgent",
            "all",
            None,
            None,
            None,
            None,
            DEMO_ACTIVITY_START + timedelta(days=14),
            None,
            visible_from,
            visible_until,
            "Registrar demo notice",
        ),
        (
            "scholarship-deadline",
            "deadline",
            "scholarship",
            "Merit scholarship application deadline",
            "Submit scholarship documents and advisor endorsements by the published deadline.",
            "high",
            "all",
            None,
            None,
            None,
            None,
            DEMO_ACTIVITY_START + timedelta(days=21),
            None,
            visible_from,
            visible_until,
            "Financial Aid demo notice",
        ),
        (
            "career-fair",
            "event",
            "career",
            "VinUni Career Fair registration",
            "Students can register for employer sessions and CV review slots.",
            "medium",
            "all",
            None,
            None,
            None,
            None,
            None,
            DEMO_ACTIVITY_START + timedelta(days=24),
            visible_from,
            visible_until,
            "Career Center demo notice",
        ),
        (
            "advising-week-cohort-2026",
            "academic",
            "advising",
            "Academic advising week for cohort 2026",
            "Cohort 2026 students should book advising meetings before registration opens.",
            "medium",
            "cohort",
            None,
            None,
            None,
            2026,
            None,
            None,
            visible_from,
            visible_until,
            "Advising demo notice",
        ),
        (
            "cecs-lab-safety",
            "academic",
            "lab_safety",
            "Required CECS lab safety training",
            "CECS students using teaching labs must complete safety training this month.",
            "urgent",
            "institute",
            "CECS",
            None,
            None,
            None,
            DEMO_ACTIVITY_START + timedelta(days=12),
            None,
            visible_from,
            visible_until,
            "CECS demo notice",
        ),
        (
            "case-writing-support",
            "event",
            "support",
            "Writing support workshop",
            "CASE writing fellows will host a workshop on academic argument and citation.",
            "low",
            "institute",
            "CASE",
            None,
            None,
            None,
            None,
            DEMO_ACTIVITY_START + timedelta(days=18),
            visible_from,
            visible_until,
            "CASE demo notice",
        ),
        (
            "library-hours-update",
            "announcement",
            "support",
            "Library hours extended before exams",
            "The library will extend evening study hours during the final exam period.",
            "low",
            "all",
            None,
            None,
            None,
            None,
            None,
            None,
            visible_from,
            visible_until,
            "Library demo notice",
        ),
        (
            "tuition-payment-reminder",
            "deadline",
            "tuition",
            "Tuition payment reminder",
            "Please review payment status and contact Student Services if support is needed.",
            "high",
            "all",
            None,
            None,
            None,
            None,
            DEMO_ACTIVITY_START + timedelta(days=30),
            None,
            visible_from,
            visible_until,
            "Student Finance demo notice",
        ),
        (
            "student-support-announcement",
            "announcement",
            "support",
            "Student support drop-in hours",
            "Student Success advisors are available for academic and wellbeing support.",
            "medium",
            "all",
            None,
            None,
            None,
            None,
            None,
            None,
            visible_from,
            visible_until,
            "Student Success demo notice",
        ),
        (
            "chs-clinical-orientation",
            "academic",
            "clinical",
            "Clinical orientation for CHS students",
            "CHS students assigned to clinical rotations must attend orientation.",
            "urgent",
            "institute",
            "CHS",
            None,
            None,
            None,
            DEMO_ACTIVITY_START + timedelta(days=16),
            DEMO_ACTIVITY_START + timedelta(days=16),
            visible_from,
            visible_until,
            "CHS demo notice",
        ),
        (
            "bus230-registration",
            "deadline",
            "course_registration",
            "BUS230 project team registration",
            "BUS230 students should confirm analytics project teams by Friday.",
            "medium",
            "course",
            "VIB",
            bus230.course_code,
            bus230.semester,
            None,
            DEMO_ACTIVITY_START + timedelta(days=9),
            None,
            visible_from,
            visible_until,
            "VIB course demo notice",
        ),
        (
            "csc330-project-showcase",
            "event",
            "project",
            "CSC330 project showcase",
            "CECS students are invited to present software engineering projects.",
            "medium",
            "course",
            "CECS",
            csc330.course_code,
            csc330.semester,
            None,
            None,
            DEMO_ACTIVITY_START + timedelta(days=34),
            visible_from,
            visible_until,
            "CECS course demo notice",
        ),
    )

    notifications: list[DemoNotification] = []
    for (
        slug,
        notification_type,
        category,
        title,
        message,
        priority,
        target_scope,
        institute_code,
        course_code,
        semester,
        cohort,
        deadline,
        event_date,
        start_date,
        end_date,
        source_title,
    ) in rows:
        notifications.append(
            DemoNotification(
                id=deterministic_uuid(f"notification:{slug}"),
                notification_type=notification_type,
                title=title,
                message=message,
                priority=priority,
                status="published",
                target_scope=target_scope,
                institute_code=institute_code,
                course_code=course_code,
                semester=semester,
                academic_year=DEMO_ACADEMIC_YEAR if course_code else None,
                cohort=cohort,
                deadline=deadline,
                event_date=event_date,
                start_date=start_date,
                end_date=end_date,
                source_title=source_title,
                source_url=None,
                created_by_email="admin.global.demo@vinuni.edu.vn",
                category=category,
            )
        )
    return notifications


def build_notification_reads(
    notifications: list[DemoNotification],
    academic_plan: DemoSeedPlan,
) -> list[DemoNotificationRead]:
    reads: list[DemoNotificationRead] = []
    readers = list(DEMO_STUDENT_EMAILS) + [
        user.email for user in academic_plan.students[4:16:2]
    ]
    for reader_index, email in enumerate(readers):
        read_count = 3 + (reader_index % 3)
        for notification in notifications[:read_count]:
            reads.append(
                DemoNotificationRead(
                    id=deterministic_uuid(f"notification-read:{notification.id}:{email}"),
                    notification_id=notification.id,
                    user_email=email,
                    read_at=DEMO_ACTIVITY_START
                    + timedelta(days=reader_index, minutes=read_count * 5),
                    important=notification.priority in {"high", "urgent"}
                    and reader_index % 2 == 0,
                )
            )
    return reads


def build_activity_events() -> list[DemoEvent]:
    rows = (
        ("career-fair", "VinUni Career Fair", "career", None, "all", True, 24),
        ("advising-week", "Academic Advising Week", "academic", None, "all", False, 7),
        ("exam-prep", "Exam Preparation Workshop", "workshop", None, "all", True, 49),
        ("club-fair", "Student Club Fair", "student_life", None, "all", False, 20),
        ("research-seminar", "Undergraduate Research Seminar", "research", None, "all", True, 28),
        ("writing-support", "Writing Support Workshop", "workshop", "CASE", "institute", True, 18),
        ("lab-safety", "Lab Safety Training", "training", "CECS", "institute", True, 12),
        (
            "clinical-orientation",
            "Health Sciences Clinical Orientation",
            "orientation",
            "CHS",
            "institute",
            True,
            16,
        ),
        (
            "business-networking",
            "Business Networking Evening",
            "networking",
            "VIB",
            "institute",
            True,
            31,
        ),
        ("cecs-showcase", "CECS Project Showcase", "showcase", "CECS", "institute", False, 34),
    )
    events: list[DemoEvent] = []
    for slug, title, event_type, institute_code, target_scope, registration_required, day in rows:
        start_time = DEMO_ACTIVITY_START + timedelta(days=day, hours=9 + day % 5)
        events.append(
            DemoEvent(
                id=deterministic_uuid(f"event:{slug}"),
                title=title,
                description=f"Synthetic demo event for {title.lower()} at VinUni.",
                event_type=event_type,
                location="VinUni Campus",
                start_time=start_time,
                end_time=start_time + timedelta(hours=2),
                institute_code=institute_code,
                target_scope=target_scope,
                registration_required=registration_required,
                registration_deadline=start_time - timedelta(days=3)
                if registration_required
                else None,
            )
        )
    return events


def build_conversations_and_messages(
    academic_plan: DemoSeedPlan,
    course_lookup: dict[tuple[str, str, str], DemoCourse],
    enrollments_by_student: dict[str, list[DemoEnrollment]],
) -> tuple[list[DemoConversation], list[DemoMessage]]:
    conversations: list[DemoConversation] = []
    messages: list[DemoMessage] = []
    topic_rows = conversation_topics_by_institute()

    for student_index, profile in enumerate(academic_plan.student_profiles):
        is_demo = profile.user_email in DEMO_STUDENT_EMAILS
        conversation_count = 4 if is_demo else student_index % 3
        institute_topics = topic_rows[profile.institute_code]
        enrollments = enrollments_by_student[profile.student_id]
        for conversation_index in range(conversation_count):
            topic = institute_topics[conversation_index % len(institute_topics)]
            course = course_lookup[
                (
                    enrollments[conversation_index % len(enrollments)].course_code,
                    DEMO_SEMESTER,
                    DEMO_ACADEMIC_YEAR,
                )
            ]
            created_at = DEMO_ACTIVITY_START + timedelta(
                days=student_index % 14,
                hours=conversation_index * 2,
            )
            conversation_id = deterministic_uuid(
                f"conversation:{profile.student_id}:{conversation_index + 1}"
            )
            message_count = 5 + conversation_index % 3 if is_demo else 2 + conversation_index % 3
            conversations.append(
                DemoConversation(
                    id=conversation_id,
                    user_email=profile.user_email,
                    title=topic["title"],
                    topic=topic["topic"],
                    created_at=created_at,
                    updated_at=created_at + timedelta(minutes=message_count * 4),
                    last_message_at=created_at + timedelta(minutes=message_count * 4),
                )
            )
            messages.extend(
                build_messages_for_conversation(
                    conversation_id,
                    profile,
                    course,
                    topic,
                    created_at,
                    message_count,
                )
            )
    return conversations, messages


def conversation_topics_by_institute() -> dict[str, tuple[dict[str, str], ...]]:
    return {
        "VIB": (
            topic_row("Scholarship eligibility", "scholarship", "financial_aid"),
            topic_row("Internship preparation", "internship", "career"),
            topic_row("Career fair registration", "career fair", "event_lookup"),
            topic_row("Course registration help", "course registration", "registration"),
        ),
        "CECS": (
            topic_row("DSA assignment support", "DSA assignment", "coursework"),
            topic_row("Lab schedule question", "lab schedule", "schedule_lookup"),
            topic_row("Project deadline planning", "project deadline", "deadline_lookup"),
            topic_row("Final exam preparation", "final exam", "exam_policy"),
        ),
        "CHS": (
            topic_row("Clinical schedule check", "clinical schedule", "schedule_lookup"),
            topic_row("Lab safety requirement", "lab safety", "training"),
            topic_row("Attendance policy question", "attendance policy", "policy_lookup"),
            topic_row("Exam regulation question", "exam regulation", "exam_policy"),
        ),
        "CASE": (
            topic_row("Elective selection", "electives", "registration"),
            topic_row("Writing support request", "writing support", "support"),
            topic_row("Campus events question", "events", "event_lookup"),
            topic_row("General education planning", "general education", "academic_planning"),
        ),
    }


def topic_row(title: str, topic: str, intent: str) -> dict[str, str]:
    return {"title": title, "topic": topic, "intent": intent}


def build_messages_for_conversation(
    conversation_id: uuid.UUID,
    profile: DemoStudentProfile,
    course: DemoCourse,
    topic: dict[str, str],
    created_at: datetime,
    message_count: int,
) -> list[DemoMessage]:
    templates = (
        (
            "user",
            f"What should I know about {topic['topic']} for {course.course_code}?",
        ),
        (
            "assistant",
            f"For {course.course_code}, check the current course page and note the nearest deadline. "
            "You can also contact your advisor for program-specific guidance.",
        ),
        (
            "user",
            "Can you summarize the next action I should take?",
        ),
        (
            "assistant",
            "A good next step is to confirm the date in your student portal and prepare any documents "
            "listed in the announcement.",
        ),
        (
            "user",
            "Is this different for my institute?",
        ),
        (
            "assistant",
            f"{profile.institute_code} may add local instructions, so watch institute announcements too.",
        ),
        (
            "assistant",
            "I can help draft a support ticket if you need staff confirmation.",
        ),
    )
    messages: list[DemoMessage] = []
    for index in range(message_count):
        role, content = templates[index % len(templates)]
        messages.append(
            DemoMessage(
                id=deterministic_uuid(f"message:{conversation_id}:{index + 1}"),
                conversation_id=conversation_id,
                role=role,
                content=content,
                intent=topic["intent"],
                topic=topic["topic"],
                confidence=Decimal("0.820") + Decimal(index % 4) / Decimal("100"),
                needs_human_review=False,
                created_at=created_at + timedelta(minutes=index * 4),
            )
        )
    return messages


def build_activity_tickets(
    academic_plan: DemoSeedPlan,
    conversations: list[DemoConversation],
) -> tuple[list[DemoTicket], list[DemoTicketMessage], list[DemoTicketStatusHistory]]:
    conversations_by_email: dict[str, list[DemoConversation]] = {}
    for conversation in conversations:
        conversations_by_email.setdefault(conversation.user_email, []).append(conversation)

    ticket_profiles = list(academic_plan.student_profiles[:16])
    demo_profiles = [
        profile for profile in academic_plan.student_profiles if profile.user_email in DEMO_STUDENT_EMAILS
    ]
    tickets: list[DemoTicket] = []
    ticket_messages: list[DemoTicketMessage] = []
    status_history: list[DemoTicketStatusHistory] = []
    status_cycle = ("submitted", "open", "in_progress", "waiting_on_student", "resolved", "closed")

    for demo_profile in demo_profiles:
        ticket_profiles.append(demo_profile)
        ticket_profiles.append(demo_profile)

    for index, profile in enumerate(ticket_profiles[:24]):
        is_demo = profile.user_email in DEMO_STUDENT_EMAILS
        status = "open" if is_demo and index % 2 == 0 else status_cycle[index % len(status_cycle)]
        if is_demo and index % 2 == 1:
            status = "resolved"
        subject = f"{profile.institute_code} support request {index + 1:02d}"
        conversation = conversations_by_email.get(profile.user_email, [None])[0]
        created_at = DEMO_ACTIVITY_START + timedelta(days=index % 20, hours=10)
        ticket_id = deterministic_uuid(f"ticket:{profile.student_id}:{index + 1}")
        tickets.append(
            DemoTicket(
                id=ticket_id,
                student_id=profile.student_id,
                institute_code=profile.institute_code,
                subject=subject,
                body=f"Please help clarify a demo academic support question for {profile.program}.",
                department=profile.institute_code,
                category=ticket_category_for_institute(profile.institute_code, index),
                priority=("medium", "high", "low", "urgent")[index % 4],
                status=status,
                source_conversation_id=conversation.id if conversation and index % 2 == 0 else None,
                origin_question=conversation.title if conversation and index % 2 == 0 else None,
                assigned_admin_email=DEMO_ADMIN_EMAIL_BY_INSTITUTE[profile.institute_code],
                submitted_at=created_at,
                due_at=created_at + timedelta(hours=48 + (index % 4) * 12),
                sla_hours=48,
                resolution="Resolved in demo data." if status in {"resolved", "closed"} else None,
                created_at=created_at,
                updated_at=created_at + timedelta(hours=8),
            )
        )
        ticket_messages.extend(
            build_ticket_messages(ticket_id, profile.user_email, status, created_at)
        )
        status_history.extend(
            build_ticket_status_history(
                ticket_id,
                profile.institute_code,
                status,
                created_at,
                index,
            )
        )
    return tickets, ticket_messages, status_history


def ticket_category_for_institute(institute_code: str, index: int) -> str:
    categories = {
        "VIB": ("scholarship", "career", "registration"),
        "CECS": ("lab", "assignment", "project"),
        "CHS": ("clinical", "attendance", "lab_safety"),
        "CASE": ("writing_support", "electives", "events"),
    }
    values = categories[institute_code]
    return values[index % len(values)]


def build_ticket_messages(
    ticket_id: uuid.UUID,
    student_email: str,
    status: str,
    created_at: datetime,
) -> list[DemoTicketMessage]:
    rows = [
        (student_email, "student", "I need help with this academic support question.", 0),
        (None, "admin", "Thanks, we are reviewing this demo request.", 45),
    ]
    if status in {"resolved", "closed"}:
        rows.append((None, "admin", "This demo request has been resolved.", 180))
    return [
        DemoTicketMessage(
            id=deterministic_uuid(f"ticket-message:{ticket_id}:{index + 1}"),
            ticket_id=ticket_id,
            sender_email=sender_email,
            author_type=author_type,
            body=body,
            created_at=created_at + timedelta(minutes=offset),
        )
        for index, (sender_email, author_type, body, offset) in enumerate(rows)
    ]


def build_ticket_status_history(
    ticket_id: uuid.UUID,
    institute_code: str,
    status: str,
    created_at: datetime,
    index: int,
) -> list[DemoTicketStatusHistory]:
    admin_email = DEMO_ADMIN_EMAIL_BY_INSTITUTE[institute_code]
    history = [
        DemoTicketStatusHistory(
            id=deterministic_uuid(f"ticket-status:{ticket_id}:submitted"),
            ticket_id=ticket_id,
            old_status=None,
            new_status="submitted",
            changed_by_email=None,
            changed_at=created_at,
        )
    ]
    if status != "submitted":
        history.append(
            DemoTicketStatusHistory(
                id=deterministic_uuid(f"ticket-status:{ticket_id}:{status}:{index}"),
                ticket_id=ticket_id,
                old_status="submitted",
                new_status=status,
                changed_by_email=admin_email,
                changed_at=created_at + timedelta(hours=2),
            )
        )
    return history


def build_question_events(
    conversations: list[DemoConversation],
    messages: list[DemoMessage],
    profiles_by_email: dict[str, DemoStudentProfile],
    course_lookup: dict[tuple[str, str, str], DemoCourse],
    enrollments_by_student: dict[str, list[DemoEnrollment]],
) -> list[DemoQuestionEvent]:
    first_user_message_by_conversation: dict[uuid.UUID, DemoMessage] = {}
    for message in messages:
        if message.role == "user" and message.conversation_id not in first_user_message_by_conversation:
            first_user_message_by_conversation[message.conversation_id] = message

    events: list[DemoQuestionEvent] = []
    for conversation in conversations:
        profile = profiles_by_email[conversation.user_email]
        enrollment = enrollments_by_student[profile.student_id][0]
        course = course_lookup[(enrollment.course_code, enrollment.semester, enrollment.academic_year)]
        first_message = first_user_message_by_conversation[conversation.id]
        normalized = first_message.content.lower().replace("?", "").strip()
        events.append(
            DemoQuestionEvent(
                id=deterministic_uuid(f"question-event:{conversation.id}"),
                user_email=conversation.user_email,
                conversation_id=conversation.id,
                raw_question=first_message.content,
                normalized_question=normalized,
                intent=first_message.intent,
                topic=conversation.topic,
                institute_code=profile.institute_code,
                course_code=course.course_code,
                semester=course.semester,
                academic_year=course.academic_year,
                created_at=first_message.created_at,
            )
        )
    return events


def build_question_trends(
    courses_by_institute: dict[str, list[DemoCourse]],
) -> list[DemoQuestionTrend]:
    trend_topics = {
        "VIB": ("internship", "scholarship", "career fair", "course registration"),
        "CECS": ("assignment deadline", "lab schedule", "project deadline", "final exam"),
        "CHS": ("clinical schedule", "attendance policy", "lab safety", "exam regulation"),
        "CASE": ("electives", "writing support", "events", "general education"),
    }
    trends: list[DemoQuestionTrend] = []
    for institute_code, topics in trend_topics.items():
        institute_courses = courses_by_institute[institute_code]
        for index, topic in enumerate(topics):
            course = institute_courses[index % len(institute_courses)] if index % 2 == 0 else None
            trends.append(
                DemoQuestionTrend(
                    id=deterministic_uuid(f"question-trend:{institute_code}:{topic}:7d"),
                    topic=topic,
                    intent=f"{topic.replace(' ', '_')}_lookup",
                    institute_code=institute_code,
                    course_code=course.course_code if course else None,
                    semester=course.semester if course else None,
                    academic_year=course.academic_year if course else None,
                    time_window="7d",
                    frequency_count=12 + index * 4 + len(institute_code),
                    trend_score=Decimal("0.610") + Decimal(index) / Decimal("20"),
                    last_seen_at=DEMO_ACTIVITY_START + timedelta(days=21 + index),
                )
            )
    return trends


def build_suggested_questions(
    notifications: list[DemoNotification],
    events: list[DemoEvent],
    tickets: list[DemoTicket],
    trends: list[DemoQuestionTrend],
    courses_by_institute: dict[str, list[DemoCourse]],
    *,
    seed_now: datetime,
) -> list[DemoSuggestedQuestion]:
    valid_from = seed_now - timedelta(days=DEMO_ACTIVITY_VISIBLE_FROM_DAYS_AGO)
    valid_until = seed_now + timedelta(days=DEMO_ACTIVITY_VISIBLE_UNTIL_DAYS)
    suggestions: list[DemoSuggestedQuestion] = []

    for trend in trends:
        suggestions.append(
            DemoSuggestedQuestion(
                id=deterministic_uuid(f"suggested-question:trend:{trend.id}"),
                question_text=f"What should I know about {trend.topic} this week?",
                source_type="trend",
                source_id=trend.id,
                notification_id=None,
                topic=trend.topic,
                intent=trend.intent,
                category="trend",
                trigger_phase="weekly",
                institute_code=trend.institute_code,
                course_code=trend.course_code,
                semester=trend.semester,
                academic_year=trend.academic_year,
                cohort=None,
                score=Decimal("7.500") + Decimal(trend.frequency_count) / Decimal("100"),
                priority=3,
                created_by_ai=True,
                approved_by_admin=True,
                is_active=True,
                valid_from=valid_from,
                valid_until=valid_until,
            )
        )

    for notification in notifications[:6]:
        suggestions.append(
            DemoSuggestedQuestion(
                id=deterministic_uuid(f"suggested-question:notification:{notification.id}"),
                question_text=f"What does the notice '{notification.title}' mean for me?",
                source_type="notification",
                source_id=notification.id,
                notification_id=notification.id,
                topic=notification.category,
                intent="notification_followup",
                category="notification",
                trigger_phase="announcement",
                institute_code=notification.institute_code,
                course_code=notification.course_code,
                semester=notification.semester,
                academic_year=notification.academic_year,
                cohort=notification.cohort,
                score=Decimal("8.200"),
                priority=4 if notification.priority in {"high", "urgent"} else 2,
                created_by_ai=True,
                approved_by_admin=True,
                is_active=True,
                valid_from=valid_from,
                valid_until=valid_until,
            )
        )

    for event in events[:4]:
        suggestions.append(
            DemoSuggestedQuestion(
                id=deterministic_uuid(f"suggested-question:event:{event.id}"),
                question_text=f"How can I register for {event.title}?",
                source_type="manual",
                source_id=event.id,
                notification_id=None,
                topic=event.event_type,
                intent="event_registration",
                category="event",
                trigger_phase="upcoming_event",
                institute_code=event.institute_code,
                course_code=None,
                semester=None,
                academic_year=None,
                cohort=None,
                score=Decimal("7.900"),
                priority=2,
                created_by_ai=False,
                approved_by_admin=True,
                is_active=True,
                valid_from=valid_from,
                valid_until=valid_until,
            )
        )

    for institute_code, courses in sorted(courses_by_institute.items()):
        course = courses[0]
        suggestions.append(
            DemoSuggestedQuestion(
                id=deterministic_uuid(f"suggested-question:deadline:{institute_code}"),
                question_text=f"Which {course.course_code} deadlines are coming up?",
                source_type="manual",
                source_id=deterministic_uuid(f"deadline-context:{institute_code}"),
                notification_id=None,
                topic="deadline",
                intent="deadline_lookup",
                category="deadline_context",
                trigger_phase="before_due_date",
                institute_code=institute_code,
                course_code=course.course_code,
                semester=course.semester,
                academic_year=course.academic_year,
                cohort=None,
                score=Decimal("8.000"),
                priority=3,
                created_by_ai=True,
                approved_by_admin=True,
                is_active=True,
                valid_from=valid_from,
                valid_until=valid_until,
            )
        )
        suggestions.append(
            DemoSuggestedQuestion(
                id=deterministic_uuid(f"suggested-question:schedule:{institute_code}"),
                question_text=f"When is my next {course.course_code} class or lab?",
                source_type="manual",
                source_id=deterministic_uuid(f"schedule-context:{institute_code}"),
                notification_id=None,
                topic="schedule",
                intent="schedule_lookup",
                category="schedule_context",
                trigger_phase="before_class",
                institute_code=institute_code,
                course_code=course.course_code,
                semester=course.semester,
                academic_year=course.academic_year,
                cohort=None,
                score=Decimal("7.850"),
                priority=3,
                created_by_ai=True,
                approved_by_admin=True,
                is_active=True,
                valid_from=valid_from,
                valid_until=valid_until,
            )
        )

    for ticket in tickets[:4]:
        suggestions.append(
            DemoSuggestedQuestion(
                id=deterministic_uuid(f"suggested-question:ticket:{ticket.id}"),
                question_text=f"How do I follow up on a {ticket.category} support request?",
                source_type="manual",
                source_id=ticket.id,
                notification_id=None,
                topic=ticket.category,
                intent="ticket_followup",
                category="ticket",
                trigger_phase="after_ticket",
                institute_code=ticket.institute_code,
                course_code=None,
                semester=None,
                academic_year=None,
                cohort=None,
                score=Decimal("7.700"),
                priority=2,
                created_by_ai=False,
                approved_by_admin=True,
                is_active=True,
                valid_from=valid_from,
                valid_until=valid_until,
            )
        )

    return suggestions


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


def activity_seed_summary_lines(plan: DemoActivitySeedPlan) -> list[str]:
    return [
        "Phase 5B demo activity seed plan:",
        f"  notifications: {len(plan.notifications)}",
        f"  notification reads: {len(plan.notification_reads)}",
        f"  events: {len(plan.events)}",
        f"  conversations: {len(plan.conversations)}",
        f"  messages: {len(plan.messages)}",
        f"  tickets: {len(plan.tickets)}",
        f"  ticket messages: {len(plan.ticket_messages)}",
        f"  ticket status history rows: {len(plan.ticket_status_history)}",
        f"  question events: {len(plan.question_events)}",
        f"  question trends: {len(plan.question_trends)}",
        f"  suggested questions: {len(plan.suggested_questions)}",
    ]


def seed_demo_data(
    settings: Settings | None = None,
    *,
    section: str = "academic",
    yes: bool = False,
) -> DemoSeedPlan | DemoActivitySeedPlan | tuple[DemoSeedPlan, DemoActivitySeedPlan]:
    if section not in {"academic", "activity", "all"}:
        raise SeedError(f"Unsupported seed section {section!r}.")
    settings = settings or get_settings()
    validate_seed_environment(settings.app_env)
    if not yes:
        raise SeedError("Demo seed requires --yes.")

    academic_plan = build_seed_plan()
    activity_plan = build_activity_seed_plan(academic_plan)
    with connect_direct(settings) as conn:
        with conn.transaction():
            if section in {"academic", "all"}:
                seed_academic_plan(conn, academic_plan)
            if section in {"activity", "all"}:
                seed_activity_plan(conn, activity_plan, academic_plan)
    if section == "activity":
        return activity_plan
    if section == "all":
        return academic_plan, activity_plan
    return academic_plan


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


def seed_activity_plan(
    conn: psycopg.Connection[Any],
    plan: DemoActivitySeedPlan,
    academic_plan: DemoSeedPlan,
) -> None:
    institute_ids = fetch_required_ids(conn, "institutes", "code", REQUIRED_INSTITUTE_CODES)
    user_ids = fetch_required_ids(conn, "users", "email", {user.email for user in academic_plan.users})
    profile_ids = fetch_required_ids(
        conn,
        "student_profiles",
        "student_id",
        {profile.student_id for profile in academic_plan.student_profiles},
    )
    course_ids = fetch_course_ids(conn, academic_plan.courses)

    upsert_notifications(conn, plan.notifications, institute_ids, course_ids, user_ids)
    upsert_notification_reads(conn, plan.notification_reads, user_ids)
    upsert_events(conn, plan.events, institute_ids)
    upsert_conversations(conn, plan.conversations, user_ids)
    upsert_messages(conn, plan.messages)
    upsert_tickets(conn, plan.tickets, profile_ids, institute_ids, user_ids)
    upsert_ticket_messages(conn, plan.ticket_messages, user_ids)
    upsert_ticket_status_history(conn, plan.ticket_status_history, user_ids)
    upsert_question_events(conn, plan.question_events, user_ids, institute_ids, course_ids)
    upsert_question_trends(conn, plan.question_trends, institute_ids, course_ids)
    upsert_suggested_questions(conn, plan.suggested_questions, institute_ids, course_ids)


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


def optional_course_id(
    course_ids: dict[tuple[str, str, str], uuid.UUID],
    course_code: str | None,
    semester: str | None,
    academic_year: str | None,
) -> uuid.UUID | None:
    if not course_code or not semester or not academic_year:
        return None
    return course_ids[(course_code, semester, academic_year)]


def upsert_notifications(
    conn: psycopg.Connection[Any],
    notifications: tuple[DemoNotification, ...],
    institute_ids: dict[str, uuid.UUID],
    course_ids: dict[tuple[str, str, str], uuid.UUID],
    user_ids: dict[str, uuid.UUID],
) -> None:
    for notification in notifications:
        conn.execute(
            """
            insert into notifications (
                id, type, title, message, priority, status, target_scope,
                institute_id, course_id, cohort, deadline, event_date, start_date,
                end_date, source_title, source_url, created_by
            )
            values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            on conflict (id) do update
            set
                type = excluded.type,
                title = excluded.title,
                message = excluded.message,
                priority = excluded.priority,
                status = excluded.status,
                target_scope = excluded.target_scope,
                institute_id = excluded.institute_id,
                course_id = excluded.course_id,
                cohort = excluded.cohort,
                deadline = excluded.deadline,
                event_date = excluded.event_date,
                start_date = excluded.start_date,
                end_date = excluded.end_date,
                source_title = excluded.source_title,
                source_url = excluded.source_url,
                created_by = excluded.created_by,
                updated_at = now()
            """,
            (
                notification.id,
                notification.notification_type,
                notification.title,
                notification.message,
                notification.priority,
                notification.status,
                notification.target_scope,
                institute_ids.get(notification.institute_code or ""),
                optional_course_id(
                    course_ids,
                    notification.course_code,
                    notification.semester,
                    notification.academic_year,
                ),
                notification.cohort,
                notification.deadline,
                notification.event_date,
                notification.start_date,
                notification.end_date,
                notification.source_title,
                notification.source_url,
                user_ids.get(notification.created_by_email or ""),
            ),
        )


def upsert_notification_reads(
    conn: psycopg.Connection[Any],
    reads: tuple[DemoNotificationRead, ...],
    user_ids: dict[str, uuid.UUID],
) -> None:
    for read in reads:
        conn.execute(
            """
            insert into notification_reads (
                id, notification_id, user_id, read_at, important, archived
            )
            values (%s, %s, %s, %s, %s, %s)
            on conflict (notification_id, user_id) do update
            set
                read_at = excluded.read_at,
                important = excluded.important,
                archived = excluded.archived
            """,
            (
                read.id,
                read.notification_id,
                user_ids[read.user_email],
                read.read_at,
                read.important,
                read.archived,
            ),
        )


def upsert_events(
    conn: psycopg.Connection[Any],
    events: tuple[DemoEvent, ...],
    institute_ids: dict[str, uuid.UUID],
) -> None:
    for event in events:
        conn.execute(
            """
            insert into events (
                id, title, description, event_type, location, start_time,
                end_time, institute_id, target_scope, registration_required,
                registration_deadline
            )
            values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            on conflict (id) do update
            set
                title = excluded.title,
                description = excluded.description,
                event_type = excluded.event_type,
                location = excluded.location,
                start_time = excluded.start_time,
                end_time = excluded.end_time,
                institute_id = excluded.institute_id,
                target_scope = excluded.target_scope,
                registration_required = excluded.registration_required,
                registration_deadline = excluded.registration_deadline
            """,
            (
                event.id,
                event.title,
                event.description,
                event.event_type,
                event.location,
                event.start_time,
                event.end_time,
                institute_ids.get(event.institute_code or ""),
                event.target_scope,
                event.registration_required,
                event.registration_deadline,
            ),
        )


def upsert_conversations(
    conn: psycopg.Connection[Any],
    conversations: tuple[DemoConversation, ...],
    user_ids: dict[str, uuid.UUID],
) -> None:
    for conversation in conversations:
        conn.execute(
            """
            insert into conversations (
                id, user_id, title, title_manual, topic, created_at, updated_at,
                last_message_at
            )
            values (%s, %s, %s, false, %s, %s, %s, %s)
            on conflict (id) do update
            set
                user_id = excluded.user_id,
                title = excluded.title,
                title_manual = false,
                topic = excluded.topic,
                updated_at = excluded.updated_at,
                last_message_at = excluded.last_message_at
            """,
            (
                conversation.id,
                user_ids[conversation.user_email],
                conversation.title,
                conversation.topic,
                conversation.created_at,
                conversation.updated_at,
                conversation.last_message_at,
            ),
        )


def upsert_messages(conn: psycopg.Connection[Any], messages: tuple[DemoMessage, ...]) -> None:
    for message in messages:
        conn.execute(
            """
            insert into messages (
                id, conversation_id, role, content, answer_json, intent, topic,
                confidence, needs_human_review, created_at
            )
            values (%s, %s, %s, %s, null, %s, %s, %s, %s, %s)
            on conflict (id) do update
            set
                conversation_id = excluded.conversation_id,
                role = excluded.role,
                content = excluded.content,
                intent = excluded.intent,
                topic = excluded.topic,
                confidence = excluded.confidence,
                needs_human_review = excluded.needs_human_review
            """,
            (
                message.id,
                message.conversation_id,
                message.role,
                message.content,
                message.intent,
                message.topic,
                message.confidence,
                message.needs_human_review,
                message.created_at,
            ),
        )


def upsert_tickets(
    conn: psycopg.Connection[Any],
    tickets: tuple[DemoTicket, ...],
    profile_ids: dict[str, uuid.UUID],
    institute_ids: dict[str, uuid.UUID],
    user_ids: dict[str, uuid.UUID],
) -> None:
    for ticket in tickets:
        conn.execute(
            """
            insert into tickets (
                id, student_profile_id, institute_id, subject, body, department,
                category, priority, status, confirmed_by_user, created_by_ai,
                include_chat_context, included_context, source_conversation_id,
                origin_question, assigned_admin_id, submitted_at, due_at, sla_hours,
                resolution, archived, deleted, created_at, updated_at
            )
            values (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, true, false, %s, null,
                %s, %s, %s, %s, %s, %s, %s, false, false, %s, %s
            )
            on conflict (id) do update
            set
                student_profile_id = excluded.student_profile_id,
                institute_id = excluded.institute_id,
                subject = excluded.subject,
                body = excluded.body,
                department = excluded.department,
                category = excluded.category,
                priority = excluded.priority,
                status = excluded.status,
                confirmed_by_user = true,
                created_by_ai = false,
                include_chat_context = excluded.include_chat_context,
                source_conversation_id = excluded.source_conversation_id,
                origin_question = excluded.origin_question,
                assigned_admin_id = excluded.assigned_admin_id,
                submitted_at = excluded.submitted_at,
                due_at = excluded.due_at,
                sla_hours = excluded.sla_hours,
                resolution = excluded.resolution,
                archived = false,
                deleted = false,
                updated_at = excluded.updated_at
            """,
            (
                ticket.id,
                profile_ids[ticket.student_id],
                institute_ids[ticket.institute_code],
                ticket.subject,
                ticket.body,
                ticket.department,
                ticket.category,
                ticket.priority,
                ticket.status,
                ticket.source_conversation_id is not None,
                ticket.source_conversation_id,
                ticket.origin_question,
                user_ids.get(ticket.assigned_admin_email or ""),
                ticket.submitted_at,
                ticket.due_at,
                ticket.sla_hours,
                ticket.resolution,
                ticket.created_at,
                ticket.updated_at,
            ),
        )


def upsert_ticket_messages(
    conn: psycopg.Connection[Any],
    messages: tuple[DemoTicketMessage, ...],
    user_ids: dict[str, uuid.UUID],
) -> None:
    for message in messages:
        conn.execute(
            """
            insert into ticket_messages (
                id, ticket_id, sender_user_id, author_type, body, created_at
            )
            values (%s, %s, %s, %s, %s, %s)
            on conflict (id) do update
            set
                ticket_id = excluded.ticket_id,
                sender_user_id = excluded.sender_user_id,
                author_type = excluded.author_type,
                body = excluded.body
            """,
            (
                message.id,
                message.ticket_id,
                user_ids.get(message.sender_email or ""),
                message.author_type,
                message.body,
                message.created_at,
            ),
        )


def upsert_ticket_status_history(
    conn: psycopg.Connection[Any],
    history_rows: tuple[DemoTicketStatusHistory, ...],
    user_ids: dict[str, uuid.UUID],
) -> None:
    for row in history_rows:
        conn.execute(
            """
            insert into ticket_status_history (
                id, ticket_id, old_status, new_status, changed_by, changed_at
            )
            values (%s, %s, %s, %s, %s, %s)
            on conflict (id) do update
            set
                ticket_id = excluded.ticket_id,
                old_status = excluded.old_status,
                new_status = excluded.new_status,
                changed_by = excluded.changed_by,
                changed_at = excluded.changed_at
            """,
            (
                row.id,
                row.ticket_id,
                row.old_status,
                row.new_status,
                user_ids.get(row.changed_by_email or ""),
                row.changed_at,
            ),
        )


def upsert_question_events(
    conn: psycopg.Connection[Any],
    question_events: tuple[DemoQuestionEvent, ...],
    user_ids: dict[str, uuid.UUID],
    institute_ids: dict[str, uuid.UUID],
    course_ids: dict[tuple[str, str, str], uuid.UUID],
) -> None:
    for event in question_events:
        conn.execute(
            """
            insert into student_question_events (
                id, user_id, conversation_id, raw_question, normalized_question,
                intent, topic, institute_id, course_id, created_at, is_anonymized
            )
            values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            on conflict (id) do update
            set
                user_id = excluded.user_id,
                conversation_id = excluded.conversation_id,
                raw_question = excluded.raw_question,
                normalized_question = excluded.normalized_question,
                intent = excluded.intent,
                topic = excluded.topic,
                institute_id = excluded.institute_id,
                course_id = excluded.course_id,
                is_anonymized = excluded.is_anonymized
            """,
            (
                event.id,
                user_ids.get(event.user_email or ""),
                event.conversation_id,
                event.raw_question,
                event.normalized_question,
                event.intent,
                event.topic,
                institute_ids.get(event.institute_code or ""),
                optional_course_id(
                    course_ids,
                    event.course_code,
                    event.semester,
                    event.academic_year,
                ),
                event.created_at,
                event.is_anonymized,
            ),
        )


def upsert_question_trends(
    conn: psycopg.Connection[Any],
    trends: tuple[DemoQuestionTrend, ...],
    institute_ids: dict[str, uuid.UUID],
    course_ids: dict[tuple[str, str, str], uuid.UUID],
) -> None:
    for trend in trends:
        conn.execute(
            """
            insert into question_trends (
                id, topic, intent, institute_id, course_id, time_window,
                frequency_count, trend_score, last_seen_at
            )
            values (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            on conflict (id) do update
            set
                topic = excluded.topic,
                intent = excluded.intent,
                institute_id = excluded.institute_id,
                course_id = excluded.course_id,
                time_window = excluded.time_window,
                frequency_count = excluded.frequency_count,
                trend_score = excluded.trend_score,
                last_seen_at = excluded.last_seen_at
            """,
            (
                trend.id,
                trend.topic,
                trend.intent,
                institute_ids.get(trend.institute_code or ""),
                optional_course_id(
                    course_ids,
                    trend.course_code,
                    trend.semester,
                    trend.academic_year,
                ),
                trend.time_window,
                trend.frequency_count,
                trend.trend_score,
                trend.last_seen_at,
            ),
        )


def upsert_suggested_questions(
    conn: psycopg.Connection[Any],
    questions: tuple[DemoSuggestedQuestion, ...],
    institute_ids: dict[str, uuid.UUID],
    course_ids: dict[tuple[str, str, str], uuid.UUID],
) -> None:
    for question in questions:
        conn.execute(
            """
            insert into suggested_questions (
                id, question_text, source_type, source_id, notification_id,
                topic, intent, category, trigger_phase, institute_id, course_id,
                cohort, score, priority, created_by_ai, approved_by_admin,
                is_active, valid_from, valid_until
            )
            values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            on conflict (id) do update
            set
                question_text = excluded.question_text,
                source_type = excluded.source_type,
                source_id = excluded.source_id,
                notification_id = excluded.notification_id,
                topic = excluded.topic,
                intent = excluded.intent,
                category = excluded.category,
                trigger_phase = excluded.trigger_phase,
                institute_id = excluded.institute_id,
                course_id = excluded.course_id,
                cohort = excluded.cohort,
                score = excluded.score,
                priority = excluded.priority,
                created_by_ai = excluded.created_by_ai,
                approved_by_admin = excluded.approved_by_admin,
                is_active = excluded.is_active,
                valid_from = excluded.valid_from,
                valid_until = excluded.valid_until,
                updated_at = now()
            """,
            (
                question.id,
                question.question_text,
                question.source_type,
                question.source_id,
                question.notification_id,
                question.topic,
                question.intent,
                question.category,
                question.trigger_phase,
                institute_ids.get(question.institute_code or ""),
                optional_course_id(
                    course_ids,
                    question.course_code,
                    question.semester,
                    question.academic_year,
                ),
                question.cohort,
                question.score,
                question.priority,
                question.created_by_ai,
                question.approved_by_admin,
                question.is_active,
                question.valid_from,
                question.valid_until,
            ),
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed Phase 5 demo data.")
    parser.add_argument(
        "--section",
        choices=["academic", "activity", "all"],
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
        academic_plan = build_seed_plan()
        if args.section in {"academic", "all"}:
            for line in seed_summary_lines(academic_plan):
                print(line)
        if args.section in {"activity", "all"}:
            activity_plan = build_activity_seed_plan(academic_plan)
            for line in activity_seed_summary_lines(activity_plan):
                print(line)
        seed_demo_data(section=args.section, yes=args.yes)
    except (MigrationError, SeedError) as exc:
        print(f"Demo seed failed: {exc}")
        return 1
    except psycopg.Error as exc:
        print(f"Demo seed failed: database error {type(exc).__name__}")
        return 1

    print("Demo data seed complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
