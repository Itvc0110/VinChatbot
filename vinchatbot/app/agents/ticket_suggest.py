"""Vinnie support-ticket draft suggestion (Part B).

A SEPARATE, small/fast LLM call (its own model: ``settings.ticket_suggest_model``, still OpenRouter) that
turns a chat turn into a reviewable ticket draft — a short summary (subject), a clear description (body),
and a category. It is advisory only: the student reviews and edits it in the drawer before anything is
sent, and the draft is flagged ``created_by_ai``.

Fail-open by design: a missing key, an LLM error, or unparsable output falls back to a deterministic
heuristic (subject = the question, body = the answer/question, category = "other") so the ticket flow
never breaks.
"""

from __future__ import annotations

import json
import logging
import re

from vinchatbot.app.agents.guardrails import answer_language
from vinchatbot.app.core.config import Settings, get_settings
from vinchatbot.app.llm.openrouter_chat import build_chat_model
from vinchatbot.app.schemas.tickets import (
    TICKET_CATEGORIES,
    SuggestedTicketDraft,
    SuggestTicketRequest,
)

logger = logging.getLogger(__name__)

_MAX_SUBJECT = 200
_MAX_BODY = 5000

_SYSTEM_EN = (
    "You are Vinnie, VinUni's student-support assistant. From the conversation below, draft a SUPPORT "
    "TICKET the student can send to a university office. Return ONLY a JSON object with exactly these "
    'keys: {"subject": "...", "body": "...", "category": "..."}.\n'
    "- subject: a BRIEF one-line TOPIC — a short noun phrase, NOT a full sentence, no ending "
    "punctuation, ideally under 80 characters, summarizing the issue "
    '(e.g. "Canvas login issue", "Retake request for CS102").\n'
    "- body: a FORMAL, polite, first-person description of the issue/request, with the concrete details "
    "from the conversation, in 2–5 sentences. Do NOT invent any facts, names, dates, or numbers that are "
    "not in the conversation. Do NOT include system text, citations, or links.\n"
    "- category: choose the SINGLE best fit by meaning:\n"
    "    academic = courses, grades, registration, curriculum, retake/improvement, graduation, academic "
    "regulations;\n"
    "    schedule = class timetable, class times, room or time conflicts;\n"
    "    student_services = housing/dormitory, library, health, campus facilities, certificates/official "
    "letters, fees/finance, student life;\n"
    "    technical = IT systems: login, Canvas, the student portal, wifi, email, software/system errors;\n"
    "    other = anything that does not clearly fit the categories above.\n"
    "Write the subject and body in the SAME LANGUAGE as the student's question. Output the JSON object "
    "only — no explanation, no markdown, no code fences."
)
# Vietnamese register: the student is filing a ticket to a university OFFICE, so the body must use the
# respectful first-person "em" and a FORMAL tone. The subject stays a short topic (no salutation).
_SYSTEM_VI_NOTE = (
    "\nCâu hỏi bằng tiếng Việt — viết subject và body bằng tiếng Việt. Trong BODY, sinh viên gửi phiếu "
    'cho phòng ban của trường nên phải xưng "em" và dùng văn phong TRANG TRỌNG, lịch sự (ví dụ: "Em xin '
    'trình bày...", "Em mong phòng ban hỗ trợ em..."). SUBJECT vẫn là một cụm chủ đề ngắn gọn, không cần '
    "xưng hô."
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


def _normalize_category(value: object) -> str:
    cat = str(value or "").strip().lower().replace(" ", "_").replace("-", "_")
    return cat if cat in TICKET_CATEGORIES else "other"


def _heuristic_draft(request: SuggestTicketRequest) -> SuggestedTicketDraft:
    """Deterministic fallback (matches the pre-Part-B client heuristic) so the drawer always opens."""
    return SuggestedTicketDraft(
        subject=(request.origin_question or "").strip()[:_MAX_SUBJECT] or "Support request",
        body=((request.answer or request.origin_question) or "").strip()[:_MAX_BODY],
        category="other",
    )


def _user_prompt(request: SuggestTicketRequest) -> str:
    parts = [f"STUDENT QUESTION:\n{request.origin_question.strip()}"]
    if request.answer and request.answer.strip():
        parts.append(f"ASSISTANT ANSWER (for context only):\n{request.answer.strip()}")
    if request.context and request.context.strip():
        parts.append(f"RECENT CONVERSATION:\n{request.context.strip()}")
    return "\n\n".join(parts)


async def suggest_ticket_draft(
    request: SuggestTicketRequest,
    settings: Settings | None = None,
) -> SuggestedTicketDraft:
    """Draft a ticket (subject/body/category) from the conversation. Fail-open to the heuristic."""
    settings = settings or get_settings()
    if not settings.openrouter_api_key:
        return _heuristic_draft(request)

    system = _SYSTEM_EN
    if answer_language(request.origin_question) == "vi":
        system = _SYSTEM_EN + _SYSTEM_VI_NOTE

    try:
        model = build_chat_model(
            settings, model=(settings.ticket_suggest_model or None), temperature=0.2
        )
        response = await model.ainvoke(
            [
                {"role": "system", "content": system},
                {"role": "user", "content": _user_prompt(request)},
            ]
        )
        obj = _parse_draft_json(_message_text(response))
        if not obj:
            return _heuristic_draft(request)
        subject = str(obj.get("subject") or "").strip()[:_MAX_SUBJECT]
        body = str(obj.get("body") or "").strip()[:_MAX_BODY]
        if not subject or not body:
            return _heuristic_draft(request)
        return SuggestedTicketDraft(
            subject=subject,
            body=body,
            category=_normalize_category(obj.get("category")),
        )
    except Exception:
        logger.warning("Ticket-draft suggestion failed; using heuristic fallback.", exc_info=True)
        return _heuristic_draft(request)
