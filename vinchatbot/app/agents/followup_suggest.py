"""Per-answer follow-up question suggestions.

A SEPARATE, small/fast LLM call (its own model: ``settings.followup_suggest_model``, still OpenRouter)
that derives the SHORT next questions a student would naturally ask Vinnie, from THIS turn's question
+ answer. It replaces the frontend's canned, rule-based chips with content-aware suggestions.

Advisory only and fail-open by design: a missing key, a disabled flag, an LLM error, or unparsable
output returns an EMPTY list so the client cleanly falls back to its own rule-based chips — the chat
turn is never affected.
"""

from __future__ import annotations

import json
import logging
import re

from vinchatbot.app.agents.guardrails import answer_language
from vinchatbot.app.core.config import Settings, get_settings
from vinchatbot.app.llm.openrouter_chat import build_chat_model

logger = logging.getLogger(__name__)

# Few and short by design — the chips sit under the answer and the questions can be long.
_MAX_ITEMS = 3
_MAX_LEN = 90

_SYSTEM_EN = (
    "You are Vinnie, VinUni's student assistant. Given the student's QUESTION and your ANSWER, propose "
    "the next questions a student would naturally ask you next. Return ONLY a JSON array of strings.\n"
    f"- At most {_MAX_ITEMS} questions; FEWER is fine. Each must be SHORT (a brief question, ideally "
    "under 10 words), phrased as the student asking (first person where natural).\n"
    "- Each must be directly related to YOUR ANSWER's content — reference the specific topic, course, "
    "person, office, or the student's own data that was discussed. No generic filler.\n"
    "- Only propose questions Vinnie can plausibly answer: VinUni information or the signed-in "
    "student's own academic data. Do NOT repeat the original question or invent facts.\n"
    "Write them in the SAME LANGUAGE as the student's question. Output the JSON array only — no prose, "
    "no markdown, no code fences."
)
_SYSTEM_VI_NOTE = (
    "\nCâu hỏi bằng tiếng Việt — viết các câu gợi ý bằng tiếng Việt, NGẮN GỌN, xưng hô tự nhiên như "
    "sinh viên đang hỏi tiếp."
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


def _parse_list(content: str) -> list[str]:
    """Pull the first JSON array of strings out of the model output (tolerant of stray prose/fences)."""
    match = re.search(r"\[.*\]", content, re.DOTALL)
    if not match:
        return []
    try:
        arr = json.loads(match.group(0))
    except (json.JSONDecodeError, ValueError):
        return []
    if not isinstance(arr, list):
        return []
    return [str(item).strip() for item in arr if isinstance(item, str) and item.strip()]


def _clean(items: list[str], original_question: str) -> list[str]:
    """De-dupe, drop the original question / over-long entries, cap the count."""
    seen: set[str] = set()
    original = original_question.strip().casefold()
    out: list[str] = []
    for item in items:
        norm = item.casefold()
        if norm == original or norm in seen or len(item) > _MAX_LEN:
            continue
        seen.add(norm)
        out.append(item)
        if len(out) >= _MAX_ITEMS:
            break
    return out


def _user_prompt(question: str, answer: str) -> str:
    return f"STUDENT QUESTION:\n{question.strip()}\n\nYOUR ANSWER:\n{answer.strip()}"


async def suggest_follow_ups(
    question: str,
    answer: str,
    settings: Settings | None = None,
) -> list[str]:
    """Suggest up to 3 short, content-derived follow-up questions. Fail-open to an empty list."""
    settings = settings or get_settings()
    if not settings.enable_followup_suggestions or not settings.openrouter_api_key:
        return []
    if not (question or "").strip() or not (answer or "").strip():
        return []

    system = _SYSTEM_EN
    if answer_language(question) == "vi":
        system = _SYSTEM_EN + _SYSTEM_VI_NOTE

    try:
        model = build_chat_model(
            settings, model=(settings.followup_suggest_model or None), temperature=0.3
        )
        response = await model.ainvoke(
            [
                {"role": "system", "content": system},
                {"role": "user", "content": _user_prompt(question, answer)},
            ]
        )
        return _clean(_parse_list(_message_text(response)), question)
    except Exception:
        logger.warning("Follow-up suggestion failed; falling back to client rules.", exc_info=True)
        return []
