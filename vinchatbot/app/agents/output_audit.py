"""Output-audit critic (Phase 1.25/B): a small LLM groundedness judge layered AFTER the deterministic
output cascade (`resolve_output_decision`). It catches the "grounded-but-wrong" residual — an answer that
cites a real document but states the wrong row/number/year — which the lenient deterministic faithfulness
check passes. On an unsupported verdict the caller converts the answer to a safe graceful-degradation.

Design (mirrors `llm_guard.classify_with_llm`): small `guard_model` (qwen-2.5-7b), temp 0, strict JSON.
NOT a PII scanner (see memory `defer-output-pii-scan-until-personalization`). Fail-OPEN: any error /
no-key / no-evidence returns `grounded=True` so a transient blip never degrades a good answer — only a
confident `grounded:false` degrades.
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field

from vinchatbot.app.core.config import Settings, get_settings
from vinchatbot.app.core.observability import record_llm_usage

logger = logging.getLogger(__name__)

AUDIT_SYSTEM = (
    "You are a strict grounding auditor for VinChatbot, a public VinUni student-support assistant. "
    "Given a user QUESTION, the assistant's ANSWER, and the retrieved EVIDENCE, decide whether every "
    "material factual claim in the ANSWER (numbers, dates, amounts, names, eligibility rules, yes/no) is "
    "directly supported by the EVIDENCE. Return JSON only: "
    '{"grounded": true|false, "unsupported_claims": ["..."], "reason": "short"}. '
    "Set grounded=false if ANY material claim is unsupported — e.g. a different year/term/row/number than the "
    "EVIDENCE states, or a claim with no support at all. "
    "Ignore phrasing, formatting, language (Vietnamese/English are equivalent), and citation/source trailers "
    "(URLs, policy codes). If the ANSWER is a refusal or says it could not find the information, return "
    "grounded=true (it asserts nothing). When in doubt and a claim plausibly matches the EVIDENCE, prefer "
    "grounded=true — only flag a clear contradiction or fabrication."
)

# Phase 1.28/D9: intent-satisfaction auditor. Groundedness ("is the claim supported") is NOT enough — an
# answer can be grounded yet not answer the SPECIFIC thing asked. The motivating case: "who is the Rector
# (Hiệu trưởng)?" answered with "Lê Mai Lan, President of the University Council" — grounded (a chunk says
# it) but the WRONG ROLE (Council-President ≠ Rector). This judge adds `satisfies_intent`: the named entity's
# role/title/attribute in the EVIDENCE must MATCH the one the QUESTION asks for; a different-but-similar role
# does not count. Same small-model / temp-0 / strict-JSON / fail-OPEN contract as the groundedness judge.
INTENT_SYSTEM = (
    "You are a strict answer-quality auditor for VinChatbot, a public VinUni student-support assistant. "
    "Given a user QUESTION, the assistant's ANSWER, and the retrieved EVIDENCE, judge TWO things and return "
    'JSON only: {"grounded": true|false, "satisfies_intent": true|false, "missing_constraints": ["..."], '
    '"reason": "short"}. '
    "(1) grounded=false if ANY material claim (number/date/amount/name/rule/yes-no) is unsupported by the "
    "EVIDENCE or contradicts it. "
    "(2) satisfies_intent=false if the ANSWER does not answer the SPECIFIC thing asked — in particular, when "
    "the QUESTION asks for a person/entity holding a SPECIFIC role, title, or attribute, the ANSWER must name "
    "an entity whose role/title/attribute IN THE EVIDENCE matches the one asked. A different-but-similar role "
    "does NOT satisfy it (e.g. asked for the Rector / Principal / Hiệu trưởng but the named person is a "
    "Council Chair / President of the Board / Vice-Rector / Provost / a different office). For 'who are the X / "
    "list all X' questions, satisfies_intent=false if the ANSWER is clearly not the authoritative or complete "
    "set (e.g. stitched together from unrelated bios). List any role/specificity gaps in missing_constraints. "
    "A refusal or 'could not find' ANSWER asserts nothing → grounded=true AND satisfies_intent=true. "
    "Ignore phrasing, formatting, language (Vietnamese/English equivalent), and citation trailers. When in "
    "genuine doubt that the answer addresses the asked role/attribute, prefer true — flag only a CLEAR "
    "role/specificity mismatch or a clearly-incomplete enumeration."
)

_EVIDENCE_CHAR_CAP = 8000


@dataclass(frozen=True)
class OutputAuditVerdict:
    grounded: bool
    unsupported_claims: list[str] = field(default_factory=list)
    reason: str = ""
    satisfies_intent: bool = True
    missing_constraints: list[str] = field(default_factory=list)


def parse_verdict(content: str) -> OutputAuditVerdict:
    """Tolerant parse (mirrors llm_guard.parse_label): default to grounded=True unless the model clearly
    says false, so a malformed/odd response never degrades a good answer."""
    text = content or ""
    m = re.search(r'"?grounded"?\s*:\s*(true|false)', text, re.IGNORECASE)
    grounded = True
    if m:
        grounded = m.group(1).lower() == "true"
    elif re.search(r"(?<!\w)(ungrounded|unsupported|not grounded|grounded\s*=\s*false)(?!\w)", text, re.IGNORECASE):
        grounded = False
    # satisfies_intent defaults True (fail-open): only a clear false degrades. Absent key (groundedness-only
    # prompt) → stays True so the groundedness path is unaffected.
    satisfies_intent = True
    sm = re.search(r'"?satisfies_intent"?\s*:\s*(true|false)', text, re.IGNORECASE)
    if sm:
        satisfies_intent = sm.group(1).lower() == "true"
    reason = ""
    rm = re.search(r'"?reason"?\s*:\s*"([^"]{0,200})"', text)
    if rm:
        reason = rm.group(1)
    missing = []
    mc = re.search(r'"?missing_constraints"?\s*:\s*\[([^\]]*)\]', text)
    if mc:
        missing = re.findall(r'"([^"]{1,120})"', mc.group(1))
    claims = re.findall(r'"([^"]{1,120})"', text)
    return OutputAuditVerdict(
        grounded=grounded,
        unsupported_claims=claims,
        reason=reason,
        satisfies_intent=satisfies_intent,
        missing_constraints=missing,
    )


async def audit_output(
    answer: str,
    retrieved_texts: list[str],
    query: str,
    settings: Settings | None = None,
    model=None,
    check_intent: bool = False,
) -> OutputAuditVerdict:
    """Judge whether `answer`'s factual claims are grounded in `retrieved_texts`. With `check_intent=True`
    (Phase 1.28/D9) ALSO judge intent-satisfaction (does the answer resolve the SPECIFIC role/attribute asked,
    not just a topically-related fact). Fail-OPEN (grounded=True, satisfies_intent=True) on any error, missing
    key, or empty evidence. `check_intent=False` keeps the groundedness-only behavior byte-identical."""
    settings = settings or get_settings()
    evidence = "\n---\n".join(t for t in retrieved_texts if t).strip()
    if not settings.openrouter_api_key or not evidence or not (answer or "").strip():
        return OutputAuditVerdict(True, [], "Auditor unavailable (no key / no evidence).")
    model_name = settings.output_audit_model or settings.guard_model
    try:
        if model is None:
            from vinchatbot.app.llm.openrouter_chat import build_chat_model

            model = build_chat_model(settings, model=model_name, temperature=0.0)
        system = INTENT_SYSTEM if check_intent else AUDIT_SYSTEM
        user = (
            f"QUESTION:\n{query}\n\nANSWER:\n{answer}\n\nEVIDENCE:\n{evidence[:_EVIDENCE_CHAR_CAP]}"
        )
        started = time.perf_counter()
        response = await model.ainvoke(
            [{"role": "system", "content": system}, {"role": "user", "content": user}]
        )
        record_llm_usage(
            "output_audit", model_name, response, (time.perf_counter() - started) * 1000
        )
        content = getattr(response, "content", response)
        if isinstance(content, list):
            content = "\n".join(
                str(item.get("text", item)) if isinstance(item, dict) else str(item) for item in content
            )
        return parse_verdict(str(content))
    except Exception:
        logger.debug("Output auditor failed; allowing (fail-open).", exc_info=True)
        return OutputAuditVerdict(True, [], "Auditor error (fail-open).")
