from __future__ import annotations

import re
import unicodedata
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Literal

from vinchatbot.app.core.config import Settings, get_settings
from vinchatbot.app.llm.openrouter_chat import build_chat_model
from vinchatbot.app.schemas.chat import ChatResponse, Citation

GuardrailAction = Literal[
    "allow",
    "greeting",
    "prompt_injection",
    "restricted_data",
    "abusive_language",
    "needs_scope_router",
    "out_of_scope",
]


@dataclass(frozen=True)
class GuardrailDecision:
    action: GuardrailAction
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
    re.compile(r"^(xin chao|chao ban|chao|alo)[!. ]*$"),
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

    if any(pattern.search(normalized) for pattern in INJECTION_PATTERNS):
        return GuardrailDecision(
            action="prompt_injection",
            reason="The request attempts to override instructions or expose protected configuration.",
        )

    if any(pattern.search(normalized) for pattern in RESTRICTED_DATA_PATTERNS):
        return GuardrailDecision(
            action="restricted_data",
            reason="The request asks for access to private student or account data.",
        )

    if any(pattern.fullmatch(normalized) for pattern in GREETING_PATTERNS):
        return GuardrailDecision(action="greeting", reason="Greeting")

    has_scope = any(_contains_term(normalized, term) for term in SCOPE_TERMS)
    has_abuse = any(pattern.search(normalized) for pattern in ABUSIVE_PATTERNS)
    has_threat = any(pattern.search(normalized) for pattern in THREAT_PATTERNS)
    if has_scope and not has_threat:
        return GuardrailDecision(action="allow", reason="VinUni student-support topic")

    if has_abuse or has_threat:
        return GuardrailDecision(
            action="abusive_language",
            reason="The request contains abusive language without a clear support question.",
        )

    if any(pattern.search(normalized) for pattern in GRAY_SCOPE_PATTERNS):
        return GuardrailDecision(
            action="needs_scope_router",
            reason="The request is ambiguous but may refer to VinUni events, dates, or schedules.",
        )

    return GuardrailDecision(
        action="out_of_scope",
        reason="The request is outside public VinUni student-support information.",
    )


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
    decision = assess_chat_input(message, filter_values)
    if decision.action != "needs_scope_router":
        return decision

    if scope_router is not None:
        return await scope_router(message)

    try:
        return await route_gray_scope_with_model(message, settings=settings)
    except Exception:
        return GuardrailDecision(
            action="allow",
            reason="Scope router unavailable; allowing ambiguous VinUni-context query.",
        )


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

    model = build_chat_model(settings)
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
    if decision.action == "greeting":
        answer = _greeting_answer(language)
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


def should_gracefully_degrade(answer: str, citations: list[Citation]) -> bool:
    if not citations:
        return True
    normalized = normalize_for_matching(answer)
    return any(marker in normalized for marker in UNKNOWN_ANSWER_MARKERS)


def contains_sensitive_output(answer: str) -> bool:
    normalized = answer.lower()
    return any(marker in normalized for marker in SENSITIVE_OUTPUT_MARKERS)


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


def _contains_term(normalized: str, term: str) -> bool:
    return re.search(rf"(?<!\w){re.escape(term)}(?!\w)", normalized) is not None


def answer_language(message: str) -> Literal["vi", "en"]:
    lowered = message.lower()
    if any(char in lowered for char in "ăâđêôơư") or any(
        token in normalize_for_matching(message).split()
        for token in ("la", "khi", "ngay", "hoc", "sinh", "vien", "toi", "ban")
    ):
        return "vi"
    return "en"


def _source_list(language: Literal["vi", "en"]) -> str:
    heading = "Nguồn chính thức nên tham khảo:" if language == "vi" else "Official sources to check:"
    links = "\n".join(f"- [{title}]({url})" for title, url in OFFICIAL_SOURCES)
    return f"{heading}\n{links}"


def _greeting_answer(language: Literal["vi", "en"]) -> str:
    if language == "vi":
        return (
            "Xin chào! Mình có thể hỗ trợ thông tin công khai dành cho sinh viên VinUni, "
            "như lịch học, deadline, chính sách, học phí và dịch vụ sinh viên."
        )
    return (
        "Hello! I can help with public VinUni student-support information such as academic "
        "calendars, deadlines, policies, fees, and student services."
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
