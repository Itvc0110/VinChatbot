from __future__ import annotations

import re
from typing import Literal

from vinchatbot.app.agents.guardrails import normalize_for_matching
from vinchatbot.app.core.observability import get_student_identity

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
    "cpa",
    "cpa tich luy",
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

# App-data nouns that are NOT inherently personal on their own (a general "what courses exist?" /
# "what is the grading scale?" is not personal). They only count as personal when paired with a
# first-person pronoun ("my grade", "điểm của tôi", "am I in good standing").
_GENERIC_APP_DATA = (
    "mon",
    "mon hoc",
    "course",
    "courses",
    "class",
    "classes",
    "enrollment",
    "enrollments",
    # academic-record nouns the personal tools can answer about the CURRENT student (Phase 5).
    "grade",
    "grades",
    "diem",
    "transcript",
    "bang diem",
    "standing",
    "academic standing",
    "hoc luc",
    "hoc vu",
    "advisor",
    "co van",
    "program",
    "major",
    "chuyen nganh",
    "curriculum",
    # class/session words (VI "lớp/tiết/buổi học") so "ngày mai tôi có lớp nào" is personal.
    "lop",
    "lop hoc",
    "tiet hoc",
    "buoi hoc",
    # "tiết" (class period) schedule phrasings — "nay tôi còn tiết nào", "tiết tiếp theo của tôi". Use
    # schedule-distinctive multiword phrases (NOT bare "tiet") to avoid colliding with "chi tiết",
    # "thời tiết", "tiết kiệm", "tiết lộ". ("tiet nao" covers "có/còn tiết nào".)
    "con tiet",
    "tiet nao",
    "may tiet",
    "tiet tiep theo",
    # student identity fields answerable by get_my_profile.
    "student id",
    "student code",
    "ma so sinh vien",
    "mssv",
    "cohort",
    "nien khoa",
)

# Personal PROGRESS / ELIGIBILITY markers (Phase 5 polish). Unlike the generic list above, these count
# as personal ONLY with an EXPLICIT first-person pronoun — NOT via the authenticated-ellipsis. Reason:
# an authenticated student also asks the GENERAL version of these ("ai đủ điều kiện học bổng?", "do most
# students graduate on time?", "what are the prerequisites for CS301?"), which has no first-person
# pronoun; gating on the pronoun routes "Am I on track to graduate?" / "Tôi có đủ điều kiện học CS301?"
# personal while leaving the general phrasings on the RAG path (precision: no over-fire). "register" /
# "đăng ký" is deliberately NOT here (would catch "how do I register for courses?").
_PERSONAL_PROGRESS = (
    "on track",
    "graduate on time",
    "tot nghiep dung han",
    "ra truong",
    "eligible",
    "eligibility",
    "du dieu kien",
    "prerequisite",
    "prerequisites",
    "tien quyet",
    "blocked",
    "bi chan",
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


# Explicit add/drop course-action terms. These denote the OFFICIAL registration procedure + its
# calendar deadline (the same for every student, with no personal-data tool), so such a question is a
# policy/calendar fact — NOT personal — even though "hạn/deadline" is otherwise inherently personal.
_OFFICIAL_COURSE_ACTION = (
    "huy mon",
    "rut mon",
    "bo mon",
    "course drop",
    "add drop",
    "add-drop",
    "drop deadline",
)

# General / catalog / org-level cues. These signal a question about the UNIVERSITY at large (what is
# offered, a program/role in the abstract) — NOT the asker's own data — so they suppress the personal
# classification (the answer belongs to the general RAG path). Deliberately TIGHT and excluding tokens
# that also appear in personal questions ("is there a class today?", "which courses am I eligible for?")
# — so "is there a", "which", "what" are NOT cues. Phase 5 fix #1 (catalog over-route).
_GENERAL_CATALOG_CUE = (
    "offer",
    "offers",
    "offered",
    "available",
    "availability",
    "typical",
    "in general",
    "list of all",
    "all programs",
    "all majors",
    "all the courses",
    "what programs",
    "which programs",
    "what majors",
    "how many programs",
    "does vinuni",
    "vinuni offer",
    "the university",
    # org-level roles (entity questions, not the student's own advisor/data)
    "dean",
    "rector",
    "provost",
    "chancellor",
    "president",
    "program director",
    "head of",
    # VI
    "truong co",
    "vinuni co",
    "danh sach",
    "hieu truong",
    "truong khoa",
    "giam doc chuong trinh",
)

# Strong first-person ownership / self-reference. Stricter than the bare pronoun list — a catalog cue is
# only allowed to suppress the personal classification when NONE of these is present, so genuinely
# personal questions ("cố vấn của tôi?", "which courses am I eligible for?") are never down-routed.
_SELF_REFERENCE = (
    "my",
    "mine",
    "cua toi",
    "cua minh",
    "cua em",
    "am i",
    "do i",
    "i have",
    "i am",
    "toi co",
    "minh co",
    "em co",
    "for me",
    "to me",
    "cho toi",
    "cho minh",
)


def _matches_any(normalized: str, terms: tuple[str, ...]) -> bool:
    return any(re.search(rf"\b{re.escape(term)}\b", normalized) for term in terms)


def classify_question_scope(
    message: str, *, authenticated: bool | None = None
) -> QuestionScope:
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

    ``authenticated``: whether a signed-in student is asking. When True, a generic app-data noun counts
    as personal even WITHOUT a first-person pronoun — a logged-in student routinely drops it ("gpa kì
    này?", "điểm CS101?", "cố vấn?"), and the session itself scopes the answer to them. Defaults to
    auto-detecting the per-request student-identity contextvar; anonymous callers keep the stricter
    pronoun requirement (precision for the public assistant).
    """
    if authenticated is None:
        authenticated = get_student_identity() is not None

    normalized = normalize_for_matching(message)
    if not normalized:
        return "general_unknown"

    has_pronoun = _matches_any(normalized, _PERSONAL_PRONOUNS)

    # A PRONOUN-LESS add/drop question is the OFFICIAL procedure / its calendar deadline (same for every
    # student, no personal tool) → policy/calendar fact, so route it to the general RAG path even though
    # "hạn/deadline" is otherwise inherently personal ("Hạn cuối hủy môn học kỳ này là khi nào?"). A
    # first-person framing ("Tôi có thể rút môn X không?") keeps the existing personal/hybrid handling.
    if not has_pronoun and _matches_any(normalized, _OFFICIAL_COURSE_ACTION):
        return "official_policy"
    has_inherent_personal = _matches_any(normalized, _INHERENT_PERSONAL_APP_DATA)
    has_generic_app_data = _matches_any(normalized, _GENERIC_APP_DATA)
    has_policy = _matches_any(normalized, _POLICY_TERMS)

    # A catalog / org-level question with NO self-reference is about the university at large, not the
    # asker's own data → suppress the personal classification so it routes to the general RAG path
    # ("what courses does VinUni offer?", "who is the dean?", "how many credits is a typical course?").
    # "is there a class today?" / "cố vấn của tôi?" are NOT suppressed (no catalog cue / self-reference).
    catalog_general = _matches_any(normalized, _GENERAL_CATALOG_CUE) and not _matches_any(
        normalized, _SELF_REFERENCE
    )

    # A progress/eligibility intent counts as personal ONLY with an explicit first-person pronoun
    # ("am I on track to graduate?", "tôi có đủ điều kiện học CS301?") — NOT via authenticated-ellipsis,
    # so the general phrasings ("who is eligible…?", "do most students graduate on time?") stay general.
    has_personal_progress = has_pronoun and _matches_any(normalized, _PERSONAL_PROGRESS)

    # A personal/app-data angle: an inherently-personal data noun, OR a generic app-data noun paired
    # with a first-person pronoun ("những môn của tôi") — or, for a signed-in student, a generic noun
    # alone, since they routinely omit the pronoun ("điểm CS101?", "cố vấn?") — or an explicit
    # first-person progress/eligibility question.
    personal_app_data = (
        has_inherent_personal
        or ((has_pronoun or authenticated) and has_generic_app_data)
        or has_personal_progress
    ) and not catalog_general

    if has_policy and (personal_app_data or has_pronoun):
        # Either an explicit personal+policy mix, or the student asking whether a rule applies to
        # them ("Tôi có đủ điều kiện học bổng này không?") — personal facts + a policy claim.
        return "hybrid"
    if has_policy:
        return "official_policy"
    if personal_app_data:
        return "personal_app_data"
    return "general_unknown"
