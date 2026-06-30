from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

CurriculumCategory = Literal[
    "general_education",
    "foundation",
    "major_core",
    "major_elective",
    "physical_education",
    "capstone",
]
RequisiteType = Literal["prerequisite", "corequisite"]
EnrollmentStatus = Literal[
    "planned",
    "enrolled",
    "completed",
    "failed",
    "withdrawn",
    "retaking",
    "improvement",
]
MeetingType = Literal[
    "lecture",
    "lab",
    "tutorial",
    "seminar",
    "exam",
    "office_hour",
    "deadline",
]


class AcademicFacultyResponse(BaseModel):
    id: uuid.UUID
    code: str
    name: str


class AcademicProgramResponse(BaseModel):
    id: uuid.UUID
    faculty_id: uuid.UUID
    code: str
    name: str
    degree_level: str
    curriculum_year: int
    total_required_credits: int


class AcademicTermResponse(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    start_date: date
    end_date: date
    academic_year: int
    term_order: int


class AcademicCourseResponse(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    name_vi: str | None = None
    credits: int
    instructor_name: str | None = None
    course_level: int | None = None
    department_code: str | None = None
    is_general_education: bool = False
    description: str | None = None


class CurriculumCourseResponse(BaseModel):
    id: uuid.UUID
    program_id: uuid.UUID
    course: AcademicCourseResponse
    category: CurriculumCategory
    is_required: bool
    suggested_year: int | None = None
    suggested_term: int | None = None
    min_required_grade_4: Decimal | None = None


class CourseRequisiteResponse(BaseModel):
    id: uuid.UUID
    course_id: uuid.UUID
    required_course: AcademicCourseResponse
    requisite_type: RequisiteType
    min_grade_4: Decimal | None = None
    note: str | None = None


class StudentCourseEnrollmentResponse(BaseModel):
    id: uuid.UUID
    student_id: uuid.UUID
    course: AcademicCourseResponse
    term: AcademicTermResponse
    section_id: uuid.UUID | None = None
    status: EnrollmentStatus
    attempt_no: int
    is_improvement: bool
    retake_of_enrollment_id: uuid.UUID | None = None
    grade_10: Decimal | None = None
    grade_4: Decimal | None = None
    letter_grade: str | None = None
    passed: bool
    earned_credits: int
    is_gpa_counted: bool
    completed_at: datetime | None = None


class RoomResponse(BaseModel):
    id: uuid.UUID
    building: str
    room_name: str
    capacity: int


class CourseSectionResponse(BaseModel):
    id: uuid.UUID
    course: AcademicCourseResponse
    term: AcademicTermResponse
    section_code: str
    instructor_name: str | None = None
    capacity: int
    status: str


class ClassMeetingResponse(BaseModel):
    id: uuid.UUID
    section_id: uuid.UUID
    course_code: str
    course_name: str
    course_name_vi: str | None = None
    title: str
    meeting_type: MeetingType
    start_at: datetime
    end_at: datetime
    room: RoomResponse | None = None
    note: str | None = None


class TranscriptSummaryResponse(BaseModel):
    student_id: uuid.UUID
    attempted_credits: int
    earned_credits: int
    gpa_credits: int
    gpa: Decimal | None = None
    counted_enrollment_ids: list[uuid.UUID] = Field(default_factory=list)


# --- Phase 13B: student-facing read API responses --------------------------------------------

CurriculumProgressStatus = Literal["completed", "in_progress", "failed", "remaining"]


class AcademicProfileResponse(BaseModel):
    id: uuid.UUID
    student_code: str | None = None
    full_name: str | None = None
    current_year: int | None = None
    cohort_year: int | None = None
    status: str | None = None
    faculty: AcademicFacultyResponse | None = None
    program: AcademicProgramResponse | None = None


class AcademicProgressSummary(BaseModel):
    earned_credits: int
    required_credits: int
    completed_required_courses: int
    remaining_required_courses: int
    progress_percent: Decimal


class ScheduleEventResponse(BaseModel):
    id: uuid.UUID
    course_code: str
    course_name: str
    course_name_vi: str | None = None
    section_code: str | None = None
    instructor_name: str | None = None
    meeting_type: MeetingType
    title: str
    start_at: datetime
    end_at: datetime
    room_name: str | None = None
    building: str | None = None
    note: str | None = None


class AcademicOverviewResponse(BaseModel):
    profile: AcademicProfileResponse
    current_term: AcademicTermResponse | None = None
    current_gpa: Decimal | None = None
    cumulative_cpa: Decimal | None = None
    earned_credits: int
    required_credits: int
    failed_courses: list[AcademicCourseResponse] = Field(default_factory=list)
    enrolled_courses: list[AcademicCourseResponse] = Field(default_factory=list)
    upcoming_meetings: list[ScheduleEventResponse] = Field(default_factory=list)
    summary: AcademicProgressSummary


class TranscriptTermGroupResponse(BaseModel):
    term: AcademicTermResponse
    enrollments: list[StudentCourseEnrollmentResponse] = Field(default_factory=list)
    term_gpa: Decimal | None = None
    cumulative_cpa: Decimal | None = None


class TranscriptResponse(BaseModel):
    student_id: uuid.UUID
    terms: list[TranscriptTermGroupResponse] = Field(default_factory=list)
    summary: TranscriptSummaryResponse


class CurriculumProgressCourseResponse(BaseModel):
    course: AcademicCourseResponse
    category: CurriculumCategory
    is_required: bool
    suggested_year: int | None = None
    suggested_term: int | None = None
    status: CurriculumProgressStatus
    grade_4: Decimal | None = None


class CurriculumProgressResponse(BaseModel):
    program: AcademicProgramResponse | None = None
    completed: list[CurriculumProgressCourseResponse] = Field(default_factory=list)
    in_progress: list[CurriculumProgressCourseResponse] = Field(default_factory=list)
    failed: list[CurriculumProgressCourseResponse] = Field(default_factory=list)
    remaining_required: list[CurriculumProgressCourseResponse] = Field(default_factory=list)
    remaining_zero_credit: list[CurriculumProgressCourseResponse] = Field(default_factory=list)
    summary: AcademicProgressSummary


class RequisiteExplanationResponse(BaseModel):
    requisite_type: RequisiteType
    required_course: AcademicCourseResponse
    min_grade_4: Decimal | None = None
    satisfied: bool
    reason: str


class EligibleCourseResponse(BaseModel):
    course: AcademicCourseResponse
    category: CurriculumCategory | None = None
    is_required: bool = True
    eligible: bool
    already_completed: bool
    currently_enrolled: bool
    can_retake_or_improve: bool
    blocking_reasons: list[str] = Field(default_factory=list)
    prerequisites: list[RequisiteExplanationResponse] = Field(default_factory=list)
    corequisites: list[RequisiteExplanationResponse] = Field(default_factory=list)


class CourseEligibilityResponse(BaseModel):
    term: AcademicTermResponse | None = None
    eligible: list[EligibleCourseResponse] = Field(default_factory=list)
    blocked: list[EligibleCourseResponse] = Field(default_factory=list)
