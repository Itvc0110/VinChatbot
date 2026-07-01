from __future__ import annotations

import re
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from vinchatbot.app.agents.form_suggest import suggest_form_fill
from vinchatbot.app.db.connection import get_app_db_pool
from vinchatbot.app.dependencies.auth import require_roles
from vinchatbot.app.repositories.auth import AuthenticatedUser
from vinchatbot.app.repositories.students import StudentRepository
from vinchatbot.app.schemas.forms import FillFormRequest, SuggestedFormFill, SuggestFormRequest
from vinchatbot.app.services.form_fill import (
    FormFetchError,
    analyze_form,
    default_form_fields,
    fetch_form_bytes,
    is_allowed_form_url,
    render_form_file,
)

router = APIRouter(tags=["forms"])
StudentUser = Annotated[AuthenticatedUser, Depends(require_roles("student"))]

_GENERATED_DOCX_NOTICE = (
    "Biểu mẫu gốc không phải dạng điền trực tiếp nên Vinnie đã tạo một bản .docx sạch để em chỉnh sửa. / "
    "The official form isn't a fillable file, so this is a clean editable .docx you can adjust."
)


def _forbid_disallowed_url(url: str) -> None:
    if not is_allowed_form_url(url):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Form URL must be an official VinUni (vinuni.edu.vn) link.",
        )


async def _personal_facts(user: AuthenticatedUser) -> dict[str, str]:
    """The signed-in student's authoritative identity facts for deterministic prefill. Isolation: we only
    ever read THIS user's own profile. Fail-soft — name/email alone are enough if the profile is missing."""
    facts: dict[str, str] = {"full_name": user.full_name, "email": user.email}
    pool = get_app_db_pool()
    if pool is not None:
        try:
            profile = await StudentRepository(pool).get_current_student_profile(user.id)
        except Exception:
            profile = None
        if profile:
            facts["student_id"] = str(profile.get("student_id") or "")
            facts["program"] = str(profile.get("program") or profile.get("major") or "")
            facts["cohort"] = str(profile.get("cohort") or "")
            facts["advisor_name"] = str(profile.get("advisor_name") or "")
    return {key: value for key, value in facts.items() if value}


def _safe_filename(form_title: str | None, ext: str) -> str:
    base = re.sub(r"[^A-Za-z0-9._-]+", "_", (form_title or "vinuni_form").strip()).strip("_")
    return f"{(base or 'vinuni_form')[:80]}.{ext}"


@router.post("/forms/suggest", response_model=SuggestedFormFill)
async def suggest_form(
    request: SuggestFormRequest,
    current_user: StudentUser,
) -> SuggestedFormFill:
    """Vinnie drafts an official form: fetches it, extracts its fields, and pre-fills them with the
    student's data + request for review before download. Advisory only — nothing is persisted. Fails open
    to a generated editable draft if the official file can't be fetched/parsed."""
    _forbid_disallowed_url(request.official_url)
    facts = await _personal_facts(current_user)
    try:
        content, content_type = await fetch_form_bytes(request.official_url)
    except FormFetchError:
        # Fetch failed but the URL is valid → generate a default-field editable draft rather than error.
        return await suggest_form_fill(
            request, default_form_fields(), facts, file_kind="docx", notice=_GENERATED_DOCX_NOTICE
        )
    file_kind, fields = analyze_form(content, content_type, request.official_url)
    notice = None if file_kind == "pdf" else _GENERATED_DOCX_NOTICE
    return await suggest_form_fill(request, fields, facts, file_kind=file_kind, notice=notice)


@router.post("/forms/fill")
async def fill_form(
    request: FillFormRequest,
    current_user: StudentUser,
) -> StreamingResponse:
    """Produce the downloadable file from the (possibly student-edited) fields and stream it. Fills the
    official AcroForm PDF in-place when possible, otherwise generates a clean .docx. Fails open to .docx."""
    _forbid_disallowed_url(request.official_url)
    content: bytes | None = None
    detected_kind = "docx"
    try:
        content, content_type = await fetch_form_bytes(request.official_url)
        detected_kind, _ = analyze_form(content, content_type, request.official_url)
    except FormFetchError:
        content = None
    file_kind = request.file_kind if request.file_kind in ("pdf", "docx") else detected_kind
    data, mime, ext = render_form_file(
        file_kind, content, request.form_title or "VinUni Form", list(request.fields)
    )
    filename = _safe_filename(request.form_title, ext)
    return StreamingResponse(
        iter([data]),
        media_type=mime,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
