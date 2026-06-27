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
    credits: int
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
