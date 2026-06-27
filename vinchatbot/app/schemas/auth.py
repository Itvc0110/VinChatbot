from __future__ import annotations

import uuid

from pydantic import BaseModel, Field, field_validator


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=1024)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()


class InstituteResponse(BaseModel):
    id: uuid.UUID
    code: str
    name_vi: str
    name_en: str


class StudentProfileResponse(BaseModel):
    id: uuid.UUID
    student_id: str
    program: str | None = None
    major: str | None = None
    cohort: int | None = None
    academic_year: int | None = None
    student_status: str
    preferred_language: str
    advisor_name: str | None = None
    advisor_email: str | None = None
    ai_personalization_enabled: bool


class CurrentUserResponse(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    preferred_name: str | None = None
    roles: list[str] = Field(default_factory=list)
    student_profile: StudentProfileResponse | None = None
    institute: InstituteResponse | None = None


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: CurrentUserResponse


class LogoutResponse(BaseModel):
    success: bool = True
