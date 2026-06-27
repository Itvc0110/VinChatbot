from __future__ import annotations

import re
from typing import Literal

from vinchatbot.app.agents.guardrails import normalize_for_matching

QuestionScope = Literal[
    "personal_app_data",
    "official_policy",
    "hybrid",
    "general_unknown",
]

# All term lists are written in NORMALIZED form (lower-case, accents stripped, đ→d) because they are
# matched against `normalize_for_matching(message)`. Match with word boundaries so short tokens
# (e.g. "mon", "me", "i") don't fire inside unrelated words.

# Personal pronouns / first-person markers — signal the question is about the asker themselves.
_PERSONAL_PRONOUNS = (
    "toi",
    "minh",
    "em",
    "cua toi",
    "cua minh",
    "cua em",
    "my",
    "mine",
    "me",
    "i",
)

# App-data nouns that are inherently about the CURRENT authenticated student's own data — these
# count as personal even without an explicit pronoun (e.g. "Có thông báo nào quan trọng không?").
_INHERENT_PERSONAL_APP_DATA = (
    "thong bao",
    "notification",
    "notifications",
    "lich",
    "lich hoc",
    "schedule",
    "thoi khoa bieu",
    "deadline",
    "deadlines",
    "han",
    "han chot",
    "han nop",
    "gpa",
    "diem trung binh",
    "credits",
    "tin chi",
    "forum",
    "dien dan",
    "topic",
    "ticket",
    "tickets",
    "yeu cau ho tro",
)

# App-data nouns that are NOT inherently personal on their own (a general "what courses exist?" is
# not personal). They only count as personal when paired with a first-person pronoun.
_GENERIC_APP_DATA = (
    "mon",
    "mon hoc",
    "course",
    "courses",
    "class",
    "classes",
    "enrollment",
    "enrollments",
)

# Official policy / regulation / institutional-fact terms — answers asserting these still require
# RAG/official citations.
_POLICY_TERMS = (
    "quy dinh",
    "quy che",
    "chinh sach",
    "policy",
    "policies",
    "regulation",
    "regulations",
    "dieu kien",
    "requirement",
    "requirements",
    "hoc phi",
    "tuition",
    "hoc bong",
    "scholarship",
    "tot nghiep",
    "graduation",
    "rut mon",
    "withdraw",
    "withdrawal",
    "add/drop",
    "add-drop",
    "add drop",
    "ky luat",
    "disciplinary",
    "admission",
    "admissions",
    "tuyen sinh",
    "registrar",
)


def _matches_any(normalized: str, terms: tuple[str, ...]) -> bool:
    return any(re.search(rf"\b{re.escape(term)}\b", normalized) for term in terms)


def classify_question_scope(message: str) -> QuestionScope:
    """Deterministically classify a chat question's scope (rule-based, no LLM).

    The result decides whether the final output guard may accept an answer that is grounded in the
    trusted backend personalization context instead of RAG/official citations:

    - ``personal_app_data`` — about the current student's own app data (notifications, schedule,
      deadlines, courses, GPA/credits, visible forum topics, tickets). May be answered from trusted
      backend context without RAG citations.
    - ``official_policy`` — about official VinUni rules/policies/regulations. Still requires
      RAG/official citations.
    - ``hybrid`` — mixes personal app-data with policy/rule claims. Personal facts may come from
      context; policy claims still require citations.
    - ``general_unknown`` — anything else; existing behavior is unchanged.
    """
    normalized = normalize_for_matching(message)
    if not normalized:
        return "general_unknown"

    has_pronoun = _matches_any(normalized, _PERSONAL_PRONOUNS)
    has_inherent_personal = _matches_any(normalized, _INHERENT_PERSONAL_APP_DATA)
    has_generic_app_data = _matches_any(normalized, _GENERIC_APP_DATA)
    has_policy = _matches_any(normalized, _POLICY_TERMS)

    # A personal/app-data angle: an inherently-personal data noun, OR a generic app-data noun paired
    # with a first-person pronoun ("những môn của tôi").
    personal_app_data = has_inherent_personal or (has_pronoun and has_generic_app_data)

    if has_policy and (personal_app_data or has_pronoun):
        # Either an explicit personal+policy mix, or the student asking whether a rule applies to
        # them ("Tôi có đủ điều kiện học bổng này không?") — personal facts + a policy claim.
        return "hybrid"
    if has_policy:
        return "official_policy"
    if personal_app_data:
        return "personal_app_data"
    return "general_unknown"
