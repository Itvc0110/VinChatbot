from __future__ import annotations

import base64
import logging
import re
import unicodedata
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Literal

from vinchatbot.app.core.config import Settings, get_settings
from vinchatbot.app.ingest.normalizer import VIETNAMESE_MARKERS
from vinchatbot.app.llm.openrouter_chat import build_chat_model
from vinchatbot.app.schemas.chat import ChatResponse, Citation

logger = logging.getLogger(__name__)

GuardrailAction = Literal[
    "allow",
    "smalltalk",
    "capability",
    "greeting",  # legacy; superseded by "smalltalk" (kept for backward compatibility)
    "prompt_injection",
    "restricted_data",
    "abusive_language",
    "needs_scope_router",
    "out_of_scope",
]

# Benign conversational turns: answered directly (no block, no retrieval) via
# build_conversational_response — distinct from blocked actions.
CONVERSATIONAL_ACTIONS = frozenset({"smalltalk", "capability"})


@dataclass(frozen=True)
class GuardrailDecision:
    action: GuardrailAction
    reason: str

    @property
    def allowed(self) -> bool:
        return self.action == "allow"


# Output-side decision (Phase 1.25/A4): the post-answer mirror of GuardrailDecision. Unifies the
# previously-inline output checks (sensitive-output / grounding) into one decision carrying a logged reason.
OutputAuditAction = Literal["allow", "sensitive_output_blocked", "graceful_degradation"]


@dataclass(frozen=True)
class OutputAuditDecision:
    action: OutputAuditAction
    reason: str

    @property
    def allowed(self) -> bool:
        return self.action == "allow"


INJECTION_PATTERNS = (
    re.compile(
        r"\b(ignore|disregard|forget|override|bypass)\b.{0,100}"
        r"\b(previous|prior|above|system|developer|instructions?|rules?|prompt)\b"
    ),
    re.compile(
        r"\b(reveal|show|print|repeat|leak|expose|extract)\b.{0,100}"
        r"\b(system prompt|developer message|hidden instructions?|api keys?|secrets?|environment variables?)\b"
    ),
    re.compile(
        r"\b(bo qua|quen|ghi de|vo hieu hoa)\b.{0,100}"
        r"\b(chi dan|quy tac|system prompt|developer prompt|lenh truoc)\b"
    ),
    re.compile(
        r"\b(tiet lo|hien thi|in ra|doc ra)\b.{0,100}"
        r"\b(system prompt|developer prompt|chi dan an|api key|bien moi truong|secret)\b"
    ),
    re.compile(
        r"\b(act as|pretend|you are now|dong vai)\b.{0,100}"
        r"\b(unrestricted|developer|system|admin|different assistant|khong bi gioi han)\b"
    ),
    re.compile(r"\b(jailbreak|dan mode|developer mode|unrestricted mode)\b"),
    re.compile(r"<\s*(system|developer|assistant)\s*>"),
)

RESTRICTED_DATA_PATTERNS = (
    re.compile(
        r"\b(show|read|check|fetch|access|retrieve|open|log into)\b.{0,80}"
        r"\b(my|someone'?s|another student'?s)\b.{0,40}"
        r"\b(grades?|email|sis|canvas|account|password|records?|transcript)\b"
    ),
    re.compile(
        r"\b(xem|doc|kiem tra|lay|truy cap|dang nhap)\b.{0,80}"
        r"\b(diem|email|sis|canvas|tai khoan|mat khau|ho so|bang diem)\b"
    ),
)

GREETING_PATTERNS = (
    re.compile(r"^(hi|hello|hey|good morning|good afternoon|good evening)[!. ]*$"),
    re.compile(r"^(xin chao|chao ban|chao|alo|chao buoi (sang|chieu|toi))[!. ]*$"),
)

# Closings / thanks / acknowledgements / reactions — FULLMATCH only, so a closing word at the
# start of a real question ("ok hạn drop môn?") is NOT swallowed. Matched on normalized text, so
# both accented ("tạm biệt") and accent-less ("tam biet") input are caught.
CLOSING_PATTERNS = (
    re.compile(r"^(ok|okay|oke|okie|kk?)[!. ]*$"),
    re.compile(r"^(uh|um+|uk|u|oh|hmm+|haha+|hihi+|hee+)[!. ]*$"),
    re.compile(r"^(duoc|duoc roi|ok roi|the thoi|vay thoi|roi)[!. ]*$"),
    re.compile(r"^(thanks|thank you|thank u|thanks a lot|ty|tks|tysm)[!. ]*$"),
    re.compile(r"^(cam on|cam on ban|cam on nhe|cam on nhieu|cam on nhe ban)[!. ]*$"),
    re.compile(r"^(tam biet|bye|goodbye|bye bye|see you|hen gap lai|chao tam biet)[!. ]*$"),
    re.compile(r"^(yes|no|yep|nope|vang|da|u|u roi)[!. ]*$"),
)

# Identity / capability / light social — SEARCH, anchored to "you/bạn" so generic "X là gì?" is
# not caught. Runs after scope-allow, so real questions that merely contain these phrases (e.g.
# "what are you allowed to tell me about fees") still route to retrieval.
CAPABILITY_PATTERNS = (
    re.compile(r"\bban la (gi|ai)\b"),
    re.compile(r"\bban la (chatbot|tro ly|ai|con gi|cai gi)\b"),
    re.compile(r"\b(what|who) are you\b"),
    re.compile(r"\bwhat can you do\b"),
    re.compile(r"\bban (lam|giup) duoc gi\b"),
    re.compile(r"\bban co the (lam|giup) (duoc )?gi\b"),
    re.compile(r"\bban (khoe khong|co khoe khong)\b"),
    re.compile(r"\bhow are you\b"),
    re.compile(r"\bban ten (la )?gi\b"),
    re.compile(r"\bwhat'?s your name\b"),
    re.compile(r"^(help|giup|giup voi|giup minh|giup toi)[!. ]*$"),
)

ABUSIVE_PATTERNS = (
    re.compile(r"\b(fuck|fucking|shit|bitch|asshole|idiot|stupid|moron)\b"),
    re.compile(r"\b(kill yourself|kys|go die)\b"),
    re.compile(r"\b(dit|du ma|duma|dm|clm|vl|vai lon|con cu|cai lon|mat day)\b"),
    re.compile(r"\b(ngu|oc cho|do dien|bien di|chet di)\b"),
)

THREAT_PATTERNS = (
    re.compile(r"\b(i will|i'm going to|im going to)\b.{0,60}\b(kill|hurt|attack|hack)\b"),
    re.compile(r"\b(tao se|toi se)\b.{0,60}\b(giet|danh|tan cong|hack|pha)\b"),
)

SCOPE_TERMS = (
    "vinuni",
    "vinuniversity",
    "student",
    "sinh vien",
    "academic",
    "hoc vu",
    "course",
    "mon hoc",
    "class",
    "lop hoc",
    "calendar",
    "lich hoc",
    "nam hoc",
    "event",
    "events",
    "su kien",
    "holiday",
    "holidays",
    "ngay le",
    "nghi le",
    "commemoration",
    "gio to",
    "semester",
    "hoc ky",
    "fall",
    "spring",
    "summer",
    "deadline",
    "han",
    "exam",
    "thi",
    "grade",
    "diem",
    "policy",
    "regulation",
    "quy dinh",
    "quy che",
    "tuition",
    "hoc phi",
    "fee",
    "scholarship",
    "hoc bong",
    "financial aid",
    "ho tro tai chinh",
    "enrollment",
    "registration",
    "dang ky",
    "course drop",
    "drop course",
    "huy mon",
    "rut mon",
    "transfer credit",
    "chuyen doi tin chi",
    "independent study",
    "graduation",
    "tot nghiep",
    "dorm",
    "residential",
    "ky tuc xa",
    "library",
    "thu vien",
    "registrar",
    "visa",
    "code of conduct",
    "conduct",
    "ky luat",
    "appeal",
    "khieu nai",
    "orientation",
    "convocation",
    "leave of absence",
    "bao luu",
    "withdrawal",
    "student gateway",
    # Broader student-life topics (Phase 1.18 guard-precision: these were missing, so legitimate
    # questions about them were over-refused). Accent-less VI forms; plurals auto via _contains_term.
    "internship",
    "thuc tap",
    "career",
    "nghe nghiep",
    "counseling",
    "counselling",
    "mental health",
    "tu van",
    "tam ly",
    "club",
    "cau lac bo",
    "housing",
    "nha o",
    "wifi",
    "internet",
    "cong nghe thong tin",
    "transcript",
    "bang diem",
    "the sinh vien",
    "clinic",
    "healthcare",
    "health",
    "y te",
    "suc khoe",
    "parking",
    "bai do xe",
    "insurance",
    "bao hiem",
)

GRAY_SCOPE_PATTERNS = (
    re.compile(r"\b(events?|event calendar|schedule|timeline|dates?)\b.{0,80}\b(20\d{2}|year|month|term)\b"),
    re.compile(r"\b(su kien|lich|moc|ngay|nam|thang)\b.{0,80}\b20\d{2}\b"),
    re.compile(r"\b(20\d{2})\b.{0,80}\b(events?|schedule|timeline|dates?|su kien|lich|moc|ngay)\b"),
)

UNKNOWN_ANSWER_MARKERS = (
    "i don't know",
    "i do not know",
    "i'm not sure",
    "i am not sure",
    "could not find",
    "couldn't find",
    "cannot find",
    "not enough evidence",
    "insufficient evidence",
    "no official source",
    "chua tim thay",
    "khong tim thay",
    "khong biet",
    "khong chac",
    "khong du bang chung",
    "khong co nguon",
    "can xac nhan",
)

SENSITIVE_OUTPUT_MARKERS = (
    "openrouter_api_key",
    "qdrant_api_key",
    "postgres_uri",
    "developer message:",
    "system prompt:",
)

OFFICIAL_SOURCES = (
    ("Student Gateway", "https://vinuni.edu.vn/student-gateway/"),
    ("Academic Calendar", "https://vinuni.edu.vn/academic-calendar/"),
    ("VinUni Policy Library", "https://policy.vinuni.edu.vn/"),
    ("Office of University Registrar", "https://registrar.vinuni.edu.vn/"),
)


def assess_user_message(message: str) -> GuardrailDecision:
    normalized = normalize_for_matching(message)
    deobfuscated = normalize_for_matching(deobfuscate(message))

    def matches(patterns: tuple[re.Pattern, ...]) -> bool:
        return any(pattern.search(normalized) or pattern.search(deobfuscated) for pattern in patterns)

    if matches(INJECTION_PATTERNS):
        return GuardrailDecision(
            action="prompt_injection",
            reason="The request attempts to override instructions or expose protected configuration.",
        )

    if matches(RESTRICTED_DATA_PATTERNS):
        return GuardrailDecision(
            action="restricted_data",
            reason="The request asks for access to private student or account data.",
        )

    # Pure greeting — friendly, before scope checks.
    if any(pattern.fullmatch(normalized) for pattern in GREETING_PATTERNS):
        return GuardrailDecision(action="smalltalk", reason="Greeting")

    has_scope = any(_contains_term(normalized, term) for term in SCOPE_TERMS)
    has_abuse = any(pattern.search(normalized) for pattern in ABUSIVE_PATTERNS)
    has_threat = any(pattern.search(normalized) for pattern in THREAT_PATTERNS)

    # A genuine in-scope question wins over the conversational/abusive heuristics (so rough
    # language inside a real support question is still allowed).
    if has_scope and not has_threat:
        return GuardrailDecision(action="allow", reason="VinUni student-support topic")

    if has_abuse or has_threat:
        return GuardrailDecision(
            action="abusive_language",
            reason="The request contains abusive language without a clear support question.",
        )

    # Identity / capability / light social ("bạn là gì", "what can you do", "bạn khỏe không").
    if any(pattern.search(normalized) for pattern in CAPABILITY_PATTERNS):
        return GuardrailDecision(action="capability", reason="Identity or capability question.")

    # Pure closing / thanks / acknowledgement / reaction (incl. emoji- or punctuation-only).
    if any(pattern.fullmatch(normalized) for pattern in CLOSING_PATTERNS) or _is_reaction_only(message):
        return GuardrailDecision(action="smalltalk", reason="Closing or acknowledgement.")

    if any(pattern.search(normalized) for pattern in GRAY_SCOPE_PATTERNS):
        return GuardrailDecision(
            action="needs_scope_router",
            reason="The request is ambiguous but may refer to VinUni events, dates, or schedules.",
        )

    return GuardrailDecision(
        action="out_of_scope",
        reason="The request is outside public VinUni student-support information.",
    )


def _is_reaction_only(message: str) -> bool:
    """True for non-empty messages with no alphanumeric word characters — pure emoji /
    punctuation reactions ("👍", ":)", "..."), which are benign acknowledgements."""
    return bool(message.strip()) and re.search(r"[0-9a-zA-ZÀ-ỹ]", message) is None


def assess_chat_input(
    message: str,
    filter_values: list[str] | None = None,
) -> GuardrailDecision:
    decision = assess_user_message(message)
    if not decision.allowed and decision.action != "needs_scope_router":
        return decision

    if filter_values:
        filter_decision = assess_user_message(" ".join(filter_values))
        if filter_decision.action in {"prompt_injection", "restricted_data"}:
            return filter_decision
    return decision


async def resolve_guardrail_decision(
    message: str,
    filter_values: list[str] | None = None,
    settings: Settings | None = None,
    scope_router: Callable[[str], Awaitable[GuardrailDecision]] | None = None,
) -> GuardrailDecision:
    settings = settings or get_settings()
    decision = assess_chat_input(message, filter_values)
    soft_scope = getattr(settings, "enable_soft_scope", False)

    # Confident regex outcomes return immediately: hard blocks, greetings, and confident
    # allows. Only the non-confident outcomes (gray zone / out-of-scope) consult the APIs,
    # so the cheap rule tier always runs first and most turns never hit a remote guard.
    confident = decision.action not in {"needs_scope_router", "out_of_scope"}
    if confident:
        if decision.allowed and settings.enable_safety_on_all:
            safety = await _run_safety_guard(message, settings)
            if not safety.allowed:
                return safety
        return decision

    # Non-confident (scope-uncertain). Security tiers still run; in soft-scope mode the SCOPE verdict
    # is downgraded to allow (off-topic is then refused downstream by graceful-degradation), but
    # injection/restricted/abusive verdicts from the safety + classifier tiers are kept as hard blocks.
    if scope_router is not None:
        return _soften_scope(await scope_router(message), soft_scope)

    safety = await _run_safety_guard(message, settings)
    if not safety.allowed:
        return safety

    if settings.enable_llm_guard and settings.openrouter_api_key:
        try:
            from vinchatbot.app.agents.llm_guard import classify_with_llm

            return _soften_scope(await classify_with_llm(message, settings=settings), soft_scope)
        except Exception:
            pass

    # No model tier available: lenient for ambiguous gray-zone queries, and (soft-scope) for off-topic.
    if decision.action == "needs_scope_router" or soft_scope:
        return GuardrailDecision(
            action="allow",
            reason="Soft-scope/ambiguous: allowed; off-topic handled by graceful-degradation.",
        )
    return decision


def _soften_scope(decision: GuardrailDecision, soft_scope: bool) -> GuardrailDecision:
    """In soft-scope mode, downgrade a SCOPE refusal to allow (off-topic is refused downstream via
    graceful-degradation). Security verdicts (injection/restricted/abusive) are left untouched."""
    if soft_scope and decision.action == "out_of_scope":
        return GuardrailDecision(
            action="allow",
            reason="Soft-scope: off-topic allowed; refused downstream if no sources found.",
        )
    return decision


async def _run_safety_guard(message: str, settings: Settings) -> GuardrailDecision:
    try:
        from vinchatbot.app.agents.safety_guard import assess_safety

        return await assess_safety(message, settings)
    except Exception:
        return GuardrailDecision(action="allow", reason="Safety guard unavailable.")


async def route_gray_scope_with_model(
    message: str,
    settings: Settings | None = None,
) -> GuardrailDecision:
    settings = settings or get_settings()
    if not settings.openrouter_api_key:
        return GuardrailDecision(
            action="allow",
            reason="No router API key; allowing ambiguous VinUni-context query.",
        )

    model = build_chat_model(settings, temperature=0.0)
    response = await model.ainvoke(
        [
            {
                "role": "system",
                "content": (
                    "You are a scope router for VinChatbot. Classify whether the user's message "
                    "should be handled by a public VinUni student-support assistant. Hard security "
                    "issues were already checked. Return JSON only: "
                    "{\"decision\":\"allow|out_of_scope\",\"reason\":\"short reason\"}. "
                    "Allow if the message is ambiguous but could reasonably refer to VinUni in this "
                    "app context, especially questions about events, dates, schedules, academic year, "
                    "deadlines, policies, admissions, student services, or campus life. Reject only "
                    "if it is clearly unrelated to VinUni/student support."
                ),
            },
            {"role": "user", "content": message},
        ]
    )
    content = _message_content(response)
    decision_text = _extract_router_decision(content)
    if decision_text == "out_of_scope":
        return GuardrailDecision(
            action="out_of_scope",
            reason="Scope router classified the request as unrelated to VinUni student support.",
        )
    return GuardrailDecision(
        action="allow",
        reason="Scope router allowed ambiguous VinUni-context query.",
    )


def build_guardrail_response(decision: GuardrailDecision, message: str) -> ChatResponse:
    language = answer_language(message)
    if decision.action in ("smalltalk", "greeting"):
        answer = _smalltalk_answer(message, language)
    elif decision.action == "capability":
        answer = _capability_answer(language)
    elif decision.action == "prompt_injection":
        answer = _prompt_injection_answer(language)
    elif decision.action == "restricted_data":
        answer = _restricted_data_answer(language)
    elif decision.action == "abusive_language":
        answer = _abusive_language_answer(language)
    else:
        answer = _out_of_scope_answer(language)

    return ChatResponse(
        answer=answer,
        citations=[],
        confidence=1.0,
        tool_trace=[
            {
                "type": "guardrail",
                "action": decision.action,
                "reason": decision.reason,
            }
        ],
        needs_human_review=False,
    )


async def build_conversational_response(
    decision: GuardrailDecision,
    message: str,
    settings: Settings | None = None,
) -> ChatResponse:
    """Answer a benign conversational turn directly — no retrieval, no refusal. Smalltalk
    (greeting/closing/ack) uses warm canned copy; capability/identity/social uses a small LLM
    persona reply (fail-open to canned). Always replies in the detected language."""
    settings = settings or get_settings()
    language = answer_language(message)
    if decision.action == "capability":
        answer = await _capability_reply(message, language, settings)
    else:  # smalltalk (greeting / closing / ack / reaction)
        answer = _smalltalk_answer(message, language)

    return ChatResponse(
        answer=answer,
        citations=[],
        confidence=1.0,
        tool_trace=[{"type": "guardrail", "action": decision.action, "reason": decision.reason}],
        needs_human_review=False,
    )


def should_gracefully_degrade(answer: str, citations: list[Citation]) -> bool:
    if not citations:
        return True
    normalized = normalize_for_matching(answer)
    return any(marker in normalized for marker in UNKNOWN_ANSWER_MARKERS)


# Leaked-secret VALUE patterns (Phase 1.18 output-guard hardening): catch an answer that echoes an
# actual key/token/connection-string, not just the literal config marker words. Deliberately specific
# (sk- prefixes, Bearer, `api_key=…`, creds-in-URL) so legit student answers never false-positive.
_SECRET_OUTPUT_PATTERNS = (
    re.compile(r"sk-or-v1-[a-z0-9]{16,}", re.IGNORECASE),
    re.compile(r"sk-proj-[A-Za-z0-9_-]{16,}"),
    re.compile(r"\bbearer\s+[A-Za-z0-9._\-]{20,}", re.IGNORECASE),
    re.compile(
        r"\b(api[_-]?key|secret[_-]?key|access[_-]?token|client[_-]?secret)\b\s*[:=]\s*\S{6,}",
        re.IGNORECASE,
    ),
    re.compile(r"postgres(?:ql)?://[^\s:@/]+:[^\s:@/]+@", re.IGNORECASE),
)


def contains_sensitive_output(answer: str) -> bool:
    # Phase 1.25/A4: defend against disguised leaks (mirrors the INPUT side's deobfuscate).
    zw_stripped = _ZERO_WIDTH_RE.sub("", answer)
    # Config MARKER words benefit from leetspeak folding ("p4ssw0rd" -> "password") and zero-width stripping.
    for normalized in (answer.lower(), zw_stripped.lower(), deobfuscate(answer).lower()):
        if any(marker in normalized for marker in SENSITIVE_OUTPUT_MARKERS):
            return True
    # Secret VALUE patterns are digit-bearing (sk-or-v1-…, bearer tokens), so leet-folding would CORRUPT
    # them — scan the raw and the zero-width-stripped forms only (the latter closes "sk-or-v1-ab<zwsp>cd…").
    for variant in (answer, zw_stripped):
        if any(pattern.search(variant) for pattern in _SECRET_OUTPUT_PATTERNS):
            return True
    return False


_FACT_TOKEN_RE = re.compile(r"\d[\d.,/-]*\d")

# The grounding check inspects the substantive answer body only. The citation/source trailer
# carries metadata digits (policy codes like "VUNI.54", URLs, reference numbers) that are
# never present in the chunk *body text* and are already validated by the citation pipeline —
# extracting them as "facts" produced false-positive degradations (a correct LOA answer was
# refused solely because its source code "VUNI.54" wasn't in the evidence).
_MD_LINK_RE = re.compile(r"\[([^\]]*)\]\([^)]*\)")
_SOURCE_LINE_RE = re.compile(
    r"(?im)^[\s>*_-]*(?:source|sources|nguồn|tài liệu|tham khảo|reference|references|policy code|mã)\b.*$"
)
_CODE_PAREN_RE = re.compile(
    r"(?i)\((?:policy code|reference number|mã[^):]*|source)\s*:[^)]*\)"
)


def _grounding_body(answer: str) -> str:
    """Strip citation/source attribution (markdown link targets, `Source:`/`Nguồn:` lines,
    `(Policy Code: …)`) so only substantive claims are grounding-checked."""
    text = _MD_LINK_RE.sub(r"\1", answer)
    text = _CODE_PAREN_RE.sub(" ", text)
    text = _SOURCE_LINE_RE.sub(" ", text)
    return text


def _canon_numbers(text: str) -> str:
    """Collapse in-number thousand separators so VI "10.000" == EN "10,000" == "10000" when grounding.
    Without this a correct VI answer ("10.000 đồng") was scored unfaithful vs an EN source ("10,000 VND")
    and wrongly degraded to a refusal (Phase 1.13b)."""
    return re.sub(r"(?<=\d)[.,](?=\d)", "", text)


def assess_faithfulness(answer: str, retrieved_texts: list[str]) -> bool:
    """Conservative output grounding check.

    If the answer asserts numeric/date/amount facts but the retrieved evidence shares none
    of them, treat it as unfaithful. Lenient by design (any overlap passes) and number-format
    agnostic (10.000 / 10,000 / 10000 compare equal) so differing VI↔EN date/number formatting
    between answer and source does not over-trigger degradation. Citation/source metadata
    (policy codes, URLs) is excluded so it is not mistaken for a claim. Returns True when the
    answer is considered grounded (or there is nothing to check).
    """

    if not retrieved_texts:
        return True  # the citation-presence guard already covers the no-evidence case
    body = _canon_numbers(normalize_for_matching(_grounding_body(answer)))
    answer_facts = {token for token in _FACT_TOKEN_RE.findall(body)}
    if not answer_facts:
        return True
    evidence = _canon_numbers(normalize_for_matching(" \n ".join(retrieved_texts)))
    # Year-grounding (Phase 1.19): catch the "graft the asked year onto a retrieved different-year row"
    # hallucination (e.g. answering "Fall 2030 → 21 Sep 2030" from a retrieved "Fall'26 → 21-Sep" chunk:
    # the day "21" is in evidence so the lenient overlap below passes, but the year 2030 is fabricated).
    # Conservative to avoid over-degrading correct answers: only applies when the evidence itself names
    # year(s), and an asserted year is OK if it is in evidence OR within ±1 of an evidence year (so an
    # academic-year label like "2026-2027" is fine when the chunk only names 2026). A year far from all
    # evidence years (2030 vs {2026,2027}) is the fabrication we degrade.
    answer_years = {int(y) for y in re.findall(r"20\d{2}", body)}
    evidence_years = {int(y) for y in re.findall(r"20\d{2}", evidence)}
    if answer_years and evidence_years:
        grounded = all(
            (str(y) in evidence) or any(abs(y - e) <= 1 for e in evidence_years)
            for y in answer_years
        )
        if not grounded:
            return False
    return any(fact in evidence for fact in answer_facts)


def resolve_output_decision(
    answer: str,
    citations: list[Citation],
    retrieved_texts: list[str],
    *,
    require_grounding: bool = True,
    trusted_app_data: bool = False,
) -> OutputAuditDecision:
    """Deterministic post-answer guard cascade (Phase 1.25/A4) — the output mirror of
    `resolve_guardrail_decision`. Unifies the previously-inline checks into one decision carrying a
    logged reason. Order: (1) sensitive-output/secret leak (always, incl. de-obfuscated form); then,
    when grounding applies, (2) no-citation / unknown-answer marker, (3) numeric/date grounding.

    `require_grounding=False` for the bypass paths (pure-time fast path, conversational/capability
    replies) — they legitimately have no citations, so only the secret scan applies.

    `trusted_app_data=True` (Phase 14A hotfix) for personal app-data answers grounded in the
    backend-owned personalization context — the current authenticated student's OWN data, built
    server-side, not RAG. Such answers legitimately have no official citations, so the citation /
    numeric-grounding requirements are skipped; only the secret scan and an explicit
    unknown-answer/decline marker still degrade. This NEVER relaxes the RAG requirement for
    policy/general questions — the caller only sets it for `personal_app_data` scope when a
    server-built context is present. It must never be derived from client-supplied input.

    Fail-closed by contract: the caller MUST treat any exception from this function as a degrade
    (never serve an un-audited answer)."""
    if contains_sensitive_output(answer):
        return OutputAuditDecision(
            "sensitive_output_blocked",
            "Answer may disclose protected configuration or a secret value.",
        )
    if not require_grounding:
        return OutputAuditDecision("allow", "No grounding required for this turn (bypass path).")
    if trusted_app_data:
        # Grounded in trusted backend personalization context (current student's own app data), not
        # RAG. Only degrade if the model itself declined / over-hedged; no citation is expected.
        if any(marker in normalize_for_matching(answer) for marker in UNKNOWN_ANSWER_MARKERS):
            return OutputAuditDecision(
                "graceful_degradation",
                "Personal app-data answer declined or found nothing in trusted context.",
            )
        return OutputAuditDecision(
            "allow",
            "Answer grounded in trusted backend personalization context (personal app data).",
        )
    if should_gracefully_degrade(answer, citations):
        return OutputAuditDecision(
            "graceful_degradation",
            "No supporting citation, or the answer is an unknown-answer/decline.",
        )
    if not assess_faithfulness(answer, retrieved_texts):
        return OutputAuditDecision(
            "graceful_degradation",
            "Answer asserts numeric/date facts not grounded in the retrieved evidence.",
        )
    return OutputAuditDecision("allow", "Answer is citation-backed and grounded in the evidence.")


def _message_content(message: object) -> str:
    content = getattr(message, "content", message)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            str(item.get("text", item)) if isinstance(item, dict) else str(item)
            for item in content
        )
    return str(content)


def _extract_router_decision(content: str) -> str:
    normalized = normalize_for_matching(content)
    if re.search(r'"?decision"?\s*:\s*"?out_of_scope"?', normalized):
        return "out_of_scope"
    if "out_of_scope" in normalized and "allow" not in normalized:
        return "out_of_scope"
    return "allow"


def build_graceful_degradation_response(
    message: str,
    citations: list[Citation] | None = None,
    tool_trace: list[dict] | None = None,
) -> ChatResponse:
    language = answer_language(message)
    trace = list(tool_trace or [])
    trace.append(
        {
            "type": "guardrail",
            "action": "graceful_degradation",
            "reason": "No sufficiently supported answer was found.",
        }
    )
    return ChatResponse(
        answer=_unknown_answer(language),
        citations=list(citations or []),
        confidence=0.0,
        tool_trace=trace,
        needs_human_review=True,
    )


def normalize_for_matching(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text.lower())
    without_accents = "".join(char for char in decomposed if unicodedata.category(char) != "Mn")
    return re.sub(r"\s+", " ", without_accents.replace("đ", "d")).strip()


_ZERO_WIDTH_RE = re.compile(r"[​-‏⁠﻿]")
_LEET_MAP = str.maketrans({"4": "a", "3": "e", "1": "i", "0": "o", "$": "s", "@": "a", "5": "s", "7": "t"})
_BASE64_RE = re.compile(r"[A-Za-z0-9+/]{16,}={0,2}")


def deobfuscate(text: str) -> str:
    """Best-effort de-obfuscation so encoded/disguised injections still match the rules:
    strip zero-width characters, fold common leetspeak, and append base64-decoded text.
    """
    stripped = _ZERO_WIDTH_RE.sub("", text)
    folded = stripped.translate(_LEET_MAP)
    decoded: list[str] = []
    for token in _BASE64_RE.findall(text):
        try:
            padded = token + "=" * ((4 - len(token) % 4) % 4)
            raw = base64.b64decode(padded, validate=False).decode("utf-8", "ignore")
        except Exception:
            continue
        # Only surface decoded text that ITSELF looks like an injection. Otherwise a benign long token
        # (an ID, hash, or URL slug a user pastes) decodes to garbage and would spuriously match a rule.
        if len(raw) >= 4 and raw.isprintable() and any(
            pattern.search(normalize_for_matching(raw)) for pattern in INJECTION_PATTERNS
        ):
            decoded.append(raw)
    return f"{folded} {' '.join(decoded)}".strip()


def scan_for_injection(text: str) -> bool:
    """True if the text contains prompt-injection patterns. Used to screen retrieved
    document content for indirect (data-borne) injection before it reaches the model.
    """
    for variant in (normalize_for_matching(text), normalize_for_matching(deobfuscate(text))):
        if any(pattern.search(variant) for pattern in INJECTION_PATTERNS):
            return True
    return False


def _contains_term(normalized: str, term: str) -> bool:
    # Allow a regular plural for longer English nouns ("event"->"events", "fee s"->"fees") without
    # over-matching short Vietnamese tokens (e.g. "thi"->"this", "han"->"hans") or multi-word terms.
    suffix = "s?" if term.isascii() and term.isalpha() and len(term) >= 4 else ""
    return re.search(rf"(?<!\w){re.escape(term)}{suffix}(?!\w)", normalized) is not None


# Accent-less Vietnamese hint words (matched on normalized tokens) so Vietnamese typed WITHOUT
# diacritics ("xin chao", "cam on", "ban la gi") is still detected as Vietnamese. Deliberately
# excludes words that collide with common English ("the", "on", "ten", "gap", "hen") to avoid
# misclassifying English questions as Vietnamese.
_VI_WORD_HINTS = frozenset(
    (
        "la", "khi", "ngay", "hoc", "sinh", "vien", "toi", "ban", "minh", "xin", "chao",
        "cam", "tam", "biet", "gi", "vay", "khong", "khoe", "oke", "vang", "duoc", "roi",
        "lai", "giup", "cua", "nhe", "voi",
    )
)


def answer_language(message: str) -> Literal["vi", "en"]:
    # Any Vietnamese diacritic → Vietnamese (the full accent set, reused from the normalizer);
    # otherwise fall back to accent-less hint words; default English.
    if any(char in VIETNAMESE_MARKERS for char in message.lower()):
        return "vi"
    if set(normalize_for_matching(message).split()) & _VI_WORD_HINTS:
        return "vi"
    return "en"


def _source_list(language: Literal["vi", "en"]) -> str:
    heading = "Nguồn chính thức nên tham khảo:" if language == "vi" else "Official sources to check:"
    links = "\n".join(f"- [{title}]({url})" for title, url in OFFICIAL_SOURCES)
    return f"{heading}\n{links}"


def _greeting_answer(language: Literal["vi", "en"]) -> str:
    if language == "vi":
        return (
            "Xin chào! Mình là VinChatbot, trợ lý hỗ trợ sinh viên VinUni. Mình có thể giúp về "
            "lịch học, deadline, quy định, học phí và dịch vụ sinh viên. Bạn cần hỏi gì nào?"
        )
    return (
        "Hi! I'm VinChatbot, VinUni's student-support assistant. I can help with academic "
        "calendars, deadlines, policies, fees, and student services. What would you like to ask?"
    )


CAPABILITY_PERSONA = (
    "Bạn là VinChatbot, trợ lý AI hỗ trợ học vụ và dịch vụ sinh viên VinUni. Hãy giới thiệu bản thân "
    "và khả năng một cách thân thiện, ngắn gọn (2-4 câu): bạn trả lời các câu hỏi về lịch học, "
    "deadline, quy định/quy chế, học phí và dịch vụ sinh viên dựa trên tài liệu chính thức và có "
    "trích dẫn nguồn; bạn không truy cập dữ liệu cá nhân (điểm, SIS, email). Mời người dùng đặt một "
    "câu hỏi học vụ cụ thể. TUYỆT ĐỐI không bịa số liệu, quy định hay mốc thời gian cụ thể, và trả "
    "lời đúng ngôn ngữ của người dùng."
)


def _capability_answer(language: Literal["vi", "en"]) -> str:
    """Canned identity/capability reply (also the fail-open fallback for the LLM persona reply)."""
    if language == "vi":
        return (
            "Mình là VinChatbot — trợ lý AI hỗ trợ học vụ VinUni. Mình trả lời các câu hỏi về lịch "
            "học, deadline, quy định, học phí và dịch vụ sinh viên, kèm trích dẫn nguồn chính thức, "
            "và không truy cập dữ liệu cá nhân. Bạn cứ hỏi mình một câu hỏi học vụ cụ thể nhé!"
        )
    return (
        "I'm VinChatbot — an AI assistant for VinUni student support. I answer questions about "
        "academic calendars, deadlines, policies, fees, and student services with citations to "
        "official sources, and I can't access personal data. Ask me a specific student-support "
        "question!"
    )


async def _capability_reply(message: str, language: Literal["vi", "en"], settings: Settings) -> str:
    """LLM persona reply for identity/capability/social turns; fail-open to the canned answer."""
    canned = _capability_answer(language)
    if not settings.openrouter_api_key:
        return canned
    directive = "Trả lời bằng tiếng Việt." if language == "vi" else "Answer in English."
    try:
        model = build_chat_model(settings)
        response = await model.ainvoke(
            [
                {"role": "system", "content": f"{CAPABILITY_PERSONA}\n\n{directive}"},
                {"role": "user", "content": message},
            ]
        )
        text = _message_content(response).strip()
        return text or canned
    except Exception:
        logger.debug("Capability persona reply failed; using canned answer.", exc_info=True)
        return canned


def _smalltalk_answer(message: str, language: Literal["vi", "en"]) -> str:
    """Warm canned reply for greeting / thanks / farewell / acknowledgement. No source list."""
    normalized = normalize_for_matching(message)
    if any(pattern.fullmatch(normalized) for pattern in GREETING_PATTERNS):
        return _greeting_answer(language)
    is_thanks = "cam on" in normalized or "thank" in normalized or "tks" in normalized
    is_farewell = any(token in normalized for token in ("tam biet", "bye", "goodbye", "hen gap lai", "see you"))
    if language == "vi":
        if is_thanks:
            return "Rất vui được giúp bạn! Nếu cần thêm thông tin học vụ, bạn cứ hỏi mình nhé."
        if is_farewell:
            return "Tạm biệt bạn! Khi cần hỗ trợ học vụ, hãy quay lại hỏi mình bất cứ lúc nào nhé."
        return (
            "Mình ở đây để hỗ trợ bạn! Bạn cứ hỏi mình về lịch học, deadline, quy định, học phí "
            "hay dịch vụ sinh viên VinUni nhé."
        )
    if is_thanks:
        return "Happy to help! Feel free to ask me anything else about VinUni student support."
    if is_farewell:
        return "Goodbye! Come back anytime you need help with VinUni academics or student services."
    return (
        "I'm here to help! Ask me about VinUni academic calendars, deadlines, policies, fees, or "
        "student services."
    )


def _prompt_injection_answer(language: Literal["vi", "en"]) -> str:
    if language == "vi":
        return (
            "Xin lỗi, mình không thể làm theo yêu cầu thay đổi hoặc tiết lộ chỉ dẫn hệ thống, "
            "cấu hình hay thông tin bảo mật. Mình chỉ có thể hỗ trợ thông tin công khai dành "
            f"cho sinh viên VinUni.\n\n{_source_list(language)}"
        )
    return (
        "Sorry, I cannot follow requests to override or reveal system instructions, configuration, "
        "or secrets. I can only help with public VinUni student-support information.\n\n"
        f"{_source_list(language)}"
    )


def _restricted_data_answer(language: Literal["vi", "en"]) -> str:
    if language == "vi":
        return (
            "Xin lỗi, mình không thể truy cập hoặc suy đoán dữ liệu riêng tư từ SIS, Canvas, "
            "email, tài khoản cá nhân hay hồ sơ sinh viên. Bạn nên đăng nhập qua kênh chính thức "
            f"hoặc liên hệ đơn vị phụ trách.\n\n{_source_list(language)}"
        )
    return (
        "Sorry, I cannot access or infer private data from SIS, Canvas, email, personal accounts, "
        "or student records. Please use the official authenticated service or contact the responsible "
        f"office.\n\n{_source_list(language)}"
    )


def _abusive_language_answer(language: Literal["vi", "en"]) -> str:
    if language == "vi":
        return (
            "Mình sẵn sàng hỗ trợ, nhưng mình cần cuộc trao đổi giữ mức tôn trọng tối thiểu. "
            "Bạn có thể hỏi lại về lịch học, deadline, chính sách, học phí hoặc dịch vụ sinh viên VinUni."
        )
    return (
        "I am here to help, but I need the conversation to stay respectful. You can ask again "
        "about VinUni academic calendars, deadlines, policies, fees, or student services."
    )


def _out_of_scope_answer(language: Literal["vi", "en"]) -> str:
    if language == "vi":
        return (
            "Xin lỗi, câu hỏi này nằm ngoài phạm vi hỗ trợ thông tin công khai dành cho sinh viên "
            f"VinUni. Bạn có thể hỏi về lịch học, deadline, chính sách hoặc dịch vụ sinh viên.\n\n"
            f"{_source_list(language)}"
        )
    return (
        "Sorry, this question is outside the scope of public VinUni student-support information. "
        "You can ask about academic calendars, deadlines, policies, or student services.\n\n"
        f"{_source_list(language)}"
    )


def _unknown_answer(language: Literal["vi", "en"]) -> str:
    if language == "vi":
        return (
            "Xin lỗi, mình chưa tìm thấy thông tin chính thức đủ rõ trong dữ liệu hiện có để trả "
            f"lời chắc chắn. Bạn nên kiểm tra các nguồn chính thức dưới đây hoặc liên hệ đơn vị "
            f"phụ trách để xác nhận.\n\n{_source_list(language)}"
        )
    return (
        "Sorry, I could not find sufficiently clear official information in the available data to "
        f"answer confidently. Please check the official sources below or contact the responsible "
        f"office for confirmation.\n\n{_source_list(language)}"
    )
