"""Form Assistant — draft an official form's field values from the conversation + the student's data.

A SEPARATE, small/fast LLM call (its own model: ``settings.form_suggest_model``, still OpenRouter) that maps
the signed-in student's known personal facts + their request onto an official form's fields, producing a
review-ready draft. Advisory only: the student edits every field in the drawer before downloading, and the
draft is flagged ``created_by_ai``.

Two guarantees:
  * Personal identity fields (name / student ID / program / email / date) are filled DETERMINISTICALLY from
    the authenticated student's record and are authoritative — the LLM cannot overwrite them with a
    hallucination.
  * Fail-open: a missing key, an LLM error, or unparsable output falls back to a deterministic heuristic
    (personal fields prefilled + reason = the student's question/answer) so the form flow never breaks.
"""

from __future__ import annotations

import json
import logging
import re

from vinchatbot.app.agents.guardrails import answer_language
from vinchatbot.app.core.config import Settings, get_settings
from vinchatbot.app.core.timeutils import now_in_vietnam
from vinchatbot.app.llm.openrouter_chat import build_chat_model
from vinchatbot.app.schemas.forms import FormField, SuggestedFormFill, SuggestFormRequest

logger = logging.getLogger(__name__)

_MAX_VALUE = 5000
_MAX_NARRATIVE = 5000

# Personal fact → the field-label/key keywords that identify a field it should fill (deterministic prefill).
_PERSONAL_FIELD_CUES: dict[str, tuple[str, ...]] = {
    "full_name": ("full name", "ho va ten", "họ và tên", "ho ten", "họ tên", "student name", "ten sinh vien"),
    "student_id": ("student id", "student code", "ma so sinh vien", "mã số sinh viên", "mssv", "ma sinh vien"),
    "program": ("program", "chuong trinh", "chương trình", "nganh", "ngành", "major", "khoa hoc"),
    "email": ("email", "e-mail", "thu dien tu", "thư điện tử"),
    "cohort": ("cohort", "khoa", "khóa", "niên khóa", "nien khoa"),
    "advisor_name": ("advisor", "co van", "cố vấn", "gvcn"),
}

_SYSTEM_EN = (
    "You are Vinnie, VinUni's student assistant. Fill an OFFICIAL university form for the signed-in student. "
    "You are given the FORM TITLE, the list of FIELDS (each has a key and a human label), the student's "
    "KNOWN PERSONAL FACTS, and the CONVERSATION. Return ONLY a JSON object with exactly these keys: "
    '{"fields": {"<field_key>": "<value>", ...}, "narrative": "..."}.\n'
    "- fields: for EACH field key, give the correct value taken from the KNOWN PERSONAL FACTS or the "
    "CONVERSATION. For a reason/purpose field, write a concise, formal first-person statement of the "
    "student's request. Leave a field as an empty string if its value is genuinely unknown.\n"
    "- narrative: one short, formal cover sentence describing the request (may be empty).\n"
    "Do NOT invent any facts (names, dates, student IDs, numbers, course codes) that are not in the KNOWN "
    "PERSONAL FACTS or the CONVERSATION. Write values in the SAME LANGUAGE as the form's field labels. "
    "Output the JSON object only — no explanation, no markdown, no code fences."
)
# Vietnamese forms are submitted to a university office → the student writes in the respectful first-person
# "em" with a FORMAL tone in any reason/narrative text.
_SYSTEM_VI_NOTE = (
    "\nBiểu mẫu bằng tiếng Việt — điền giá trị bằng tiếng Việt. Ở các trường lý do/nội dung và ở narrative, "
    'sinh viên nộp đơn cho phòng ban của trường nên xưng "em" và dùng văn phong TRANG TRỌNG, lịch sự '
    '(ví dụ: "Em xin trình bày...", "Em kính mong nhà trường xem xét...").'
)


def _message_text(response: object) -> str:
    content = getattr(response, "content", response)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            str(item.get("text", item)) if isinstance(item, dict) else str(item) for item in content
        )
    return str(content)


def _parse_draft_json(content: str) -> dict | None:
    """Pull the first JSON object out of the model output (tolerant of stray prose / code fences)."""
    match = re.search(r"\{.*\}", content, re.DOTALL)
    if not match:
        return None
    try:
        obj = json.loads(match.group(0))
    except (json.JSONDecodeError, ValueError):
        return None
    return obj if isinstance(obj, dict) else None


def _field_matches(field: FormField, cues: tuple[str, ...]) -> bool:
    # Normalize underscores/hyphens to spaces so an AcroForm field key like "full_name" matches the
    # "full name" cue (widget fields expose only the raw key as both key and label).
    haystack = f"{field.key} {field.label}".lower().replace("_", " ").replace("-", " ")
    return any(cue in haystack for cue in cues)


def _today_str() -> str:
    return now_in_vietnam().strftime("%d/%m/%Y")


def _prefill_personal(fields: list[FormField], facts: dict[str, str]) -> None:
    """Fill identity fields IN PLACE from the authenticated student's record (authoritative)."""
    for field in fields:
        for fact_key, cues in _PERSONAL_FIELD_CUES.items():
            value = facts.get(fact_key)
            if value and _field_matches(field, cues):
                field.value = value
                break
        else:
            # Date fields default to today when empty.
            if not field.value and _field_matches(field, ("date", "ngay", "ngày")):
                field.value = _today_str()


def _heuristic_fill(
    request: SuggestFormRequest,
    fields: list[FormField],
    facts: dict[str, str],
    file_kind: str,
    notice: str | None,
) -> SuggestedFormFill:
    """Deterministic fallback: personal fields prefilled + reason/subject from the conversation."""
    _prefill_personal(fields, facts)
    reason = (request.answer or request.origin_question or "").strip()[:_MAX_VALUE]
    for field in fields:
        if field.value:
            continue
        if _field_matches(field, ("reason", "ly do", "lý do", "noi dung", "nội dung", "purpose", "content")):
            field.value = reason
        elif _field_matches(field, ("subject", "tieu de", "tiêu đề", "chu de", "chủ đề")):
            field.value = (request.form_title or request.origin_question or "").strip()[:_MAX_VALUE]
    return SuggestedFormFill(
        form_title=request.form_title or "VinUni Form",
        official_url=request.official_url,
        file_kind=file_kind,
        fields=fields,
        narrative="",
        created_by_ai=False,
        notice=notice,
    )


def _user_prompt(
    request: SuggestFormRequest, fields: list[FormField], facts: dict[str, str]
) -> str:
    field_lines = "\n".join(f'- {field.key}: "{field.label}"' for field in fields)
    fact_lines = "\n".join(f"- {key}: {value}" for key, value in facts.items() if value)
    parts = [
        f"FORM TITLE:\n{request.form_title or '(unknown)'}",
        f"FIELDS (key: label):\n{field_lines or '(none)'}",
        f"KNOWN PERSONAL FACTS:\n{fact_lines or '(none)'}",
        f"STUDENT REQUEST:\n{request.origin_question.strip()}",
    ]
    if request.answer and request.answer.strip():
        parts.append(f"ASSISTANT ANSWER (context only):\n{request.answer.strip()}")
    if request.context and request.context.strip():
        parts.append(f"RECENT CONVERSATION:\n{request.context.strip()}")
    return "\n\n".join(parts)


async def suggest_form_fill(
    request: SuggestFormRequest,
    fields: list[FormField],
    personal_facts: dict[str, str],
    file_kind: str = "docx",
    settings: Settings | None = None,
    notice: str | None = None,
) -> SuggestedFormFill:
    """Draft field values for a form. Personal identity fields are authoritative; fail-open to heuristic."""
    settings = settings or get_settings()
    # Work on copies so the caller's field list is never mutated in place.
    draft_fields = [field.model_copy() for field in fields]

    if not settings.openrouter_api_key:
        return _heuristic_fill(request, draft_fields, personal_facts, file_kind, notice)

    system = _SYSTEM_EN
    if answer_language(request.form_title or request.origin_question) == "vi":
        system = _SYSTEM_EN + _SYSTEM_VI_NOTE

    try:
        model = build_chat_model(
            settings, model=(settings.form_suggest_model or None), temperature=0.2
        )
        response = await model.ainvoke(
            [
                {"role": "system", "content": system},
                {"role": "user", "content": _user_prompt(request, draft_fields, personal_facts)},
            ]
        )
        obj = _parse_draft_json(_message_text(response))
        if not obj:
            return _heuristic_fill(request, draft_fields, personal_facts, file_kind, notice)
        llm_fields = obj.get("fields") or {}
        if isinstance(llm_fields, dict):
            for field in draft_fields:
                value = llm_fields.get(field.key)
                if value is not None and str(value).strip():
                    field.value = str(value).strip()[:_MAX_VALUE]
        narrative = str(obj.get("narrative") or "").strip()[:_MAX_NARRATIVE]
        # Personal identity fields are filled LAST so a hallucinated name/ID can never win.
        _prefill_personal(draft_fields, personal_facts)
        return SuggestedFormFill(
            form_title=request.form_title or "VinUni Form",
            official_url=request.official_url,
            file_kind=file_kind,
            fields=draft_fields,
            narrative=narrative,
            created_by_ai=True,
            notice=notice,
        )
    except Exception:
        logger.warning("Form-fill suggestion failed; using heuristic fallback.", exc_info=True)
        return _heuristic_fill(request, draft_fields, personal_facts, file_kind, notice)
