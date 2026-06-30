from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

VOTE_TARGET_TYPES = {"topic", "comment"}
MAX_TAGS = 8
MAX_ATTACHMENTS = 8
MAX_MENTIONS = 20


class ForumAttachment(BaseModel):
    url: str = Field(min_length=1, max_length=2000)
    label: str | None = Field(default=None, max_length=200)


class ForumCategoryResponse(BaseModel):
    id: uuid.UUID
    slug: str
    name_en: str
    name_vi: str
    description_en: str | None = None
    description_vi: str | None = None
    color: str
    sort_order: int
    is_active: bool
    topic_count: int = 0


class ForumMemberResponse(BaseModel):
    id: uuid.UUID
    full_name: str
    preferred_name: str | None = None
    email: str | None = None


class ForumCommentResponse(BaseModel):
    id: uuid.UUID
    topic_id: uuid.UUID
    parent_comment_id: uuid.UUID | None = None
    author_user_id: uuid.UUID | None = None
    author_name: str | None = None
    author_roles: list[str] = Field(default_factory=list)
    content: str
    is_official: bool
    deleted: bool
    score: int = 0
    my_vote: int = 0
    created_at: datetime
    updated_at: datetime
    replies: list[ForumCommentResponse] = Field(default_factory=list)


class ForumTopicSummary(BaseModel):
    id: uuid.UUID
    category_id: uuid.UUID
    category_slug: str | None = None
    category_name_en: str | None = None
    category_name_vi: str | None = None
    author_user_id: uuid.UUID | None = None
    author_name: str | None = None
    author_roles: list[str] = Field(default_factory=list)
    title: str
    excerpt: str | None = None
    tags: list[str] = Field(default_factory=list)
    is_pinned: bool
    is_locked: bool
    deleted: bool = False
    has_official_answer: bool = False
    view_count: int
    comment_count: int = 0
    score: int = 0
    my_vote: int = 0
    created_at: datetime
    updated_at: datetime
    last_activity_at: datetime


class ForumTopicDetail(ForumTopicSummary):
    content: str
    attachments: list[ForumAttachment] = Field(default_factory=list)
    official_comment_id: uuid.UUID | None = None
    comments: list[ForumCommentResponse] = Field(default_factory=list)


def _clean_tags(value: list[str]) -> list[str]:
    cleaned: list[str] = []
    for tag in value:
        normalized = tag.strip().lower().lstrip("#")
        if normalized and normalized not in cleaned and len(normalized) <= 40:
            cleaned.append(normalized)
    return cleaned[:MAX_TAGS]


def _strip_required(value: str) -> str:
    stripped = value.strip()
    if not stripped:
        raise ValueError("value must not be blank")
    return stripped


class CreateTopicRequest(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    content: str = Field(min_length=1, max_length=10000)
    category_id: uuid.UUID | None = None
    category_slug: str | None = Field(default=None, max_length=80)
    tags: list[str] = Field(default_factory=list, max_length=MAX_TAGS)
    attachments: list[ForumAttachment] = Field(default_factory=list, max_length=MAX_ATTACHMENTS)
    mentioned_user_ids: list[uuid.UUID] = Field(default_factory=list, max_length=MAX_MENTIONS)

    @field_validator("title", "content")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        return _strip_required(value)

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, value: list[str]) -> list[str]:
        return _clean_tags(value)


class CreateCommentRequest(BaseModel):
    content: str = Field(min_length=1, max_length=10000)
    parent_comment_id: uuid.UUID | None = None
    mentioned_user_ids: list[uuid.UUID] = Field(default_factory=list, max_length=MAX_MENTIONS)

    @field_validator("content")
    @classmethod
    def normalize_content(cls, value: str) -> str:
        return _strip_required(value)


class ForumTopicPatchRequest(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=200)
    content: str | None = Field(default=None, min_length=1, max_length=10000)
    category_id: uuid.UUID | None = None
    category_slug: str | None = Field(default=None, max_length=80)
    tags: list[str] | None = Field(default=None, max_length=MAX_TAGS)
    attachments: list[ForumAttachment] | None = Field(default=None, max_length=MAX_ATTACHMENTS)
    mentioned_user_ids: list[uuid.UUID] | None = Field(default=None, max_length=MAX_MENTIONS)
    is_pinned: bool | None = None
    is_locked: bool | None = None
    deleted: bool | None = None
    official_comment_id: uuid.UUID | None = None

    @field_validator("title", "content")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        return _strip_required(value) if value is not None else None

    @field_validator("tags")
    @classmethod
    def normalize_optional_tags(cls, value: list[str] | None) -> list[str] | None:
        return _clean_tags(value) if value is not None else None


class ForumCommentPatchRequest(BaseModel):
    content: str | None = Field(default=None, min_length=1, max_length=10000)
    is_official: bool | None = None
    deleted: bool | None = None

    @field_validator("content")
    @classmethod
    def normalize_optional_content(cls, value: str | None) -> str | None:
        return _strip_required(value) if value is not None else None


class VoteRequest(BaseModel):
    value: int

    @field_validator("value")
    @classmethod
    def validate_value(cls, value: int) -> int:
        if value not in (-1, 0, 1):
            raise ValueError("value must be -1, 0, or 1")
        return value


class VoteResponse(BaseModel):
    target_type: str
    target_id: uuid.UUID
    score: int
    my_vote: int


class CreateReportRequest(BaseModel):
    target_type: str
    target_id: uuid.UUID
    reason: str = Field(min_length=1, max_length=2000)

    @field_validator("target_type")
    @classmethod
    def validate_target_type(cls, value: str) -> str:
        target_type = value.strip().lower()
        if target_type not in VOTE_TARGET_TYPES:
            allowed = ", ".join(sorted(VOTE_TARGET_TYPES))
            raise ValueError(f"target_type must be one of: {allowed}")
        return target_type


class ForumReportResponse(BaseModel):
    id: uuid.UUID
    reporter_user_id: uuid.UUID | None = None
    target_type: str
    target_id: uuid.UUID
    reason: str
    status: str
    created_at: datetime


class ModerateTopicRequest(BaseModel):
    is_pinned: bool | None = None
    is_locked: bool | None = None
    deleted: bool | None = None
    official_comment_id: uuid.UUID | None = None


class ModerateCommentRequest(BaseModel):
    is_official: bool | None = None
    deleted: bool | None = None


class ForumTopicNotificationRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    message: str | None = Field(default=None, min_length=1, max_length=5000)
    priority: str = Field(default="medium")
    target_scope: str | None = None
    institute_id: uuid.UUID | None = None
    publish: bool = True

    @field_validator("title", "message")
    @classmethod
    def normalize_optional_nonblank_text(cls, value: str | None) -> str | None:
        return _strip_required(value) if value is not None else None

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, value: str) -> str:
        if value not in {"low", "medium", "high", "urgent"}:
            raise ValueError("Invalid notification priority.")
        return value

    @field_validator("target_scope")
    @classmethod
    def validate_target_scope(cls, value: str | None) -> str | None:
        if value is not None and value not in {"all", "institute"}:
            raise ValueError("Invalid notification target scope.")
        return value


# Self-referencing model (ForumCommentResponse.replies) — resolve the forward reference.
ForumCommentResponse.model_rebuild()
