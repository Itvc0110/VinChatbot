from __future__ import annotations

import json
import logging
import time
from collections.abc import Iterable
from typing import Any

from vinchatbot.app.agents.graph import build_agent_graph
from vinchatbot.app.agents.guardrails import (
    CONVERSATIONAL_ACTIONS,
    OutputAuditDecision,
    answer_language,
    assess_user_message,
    build_conversational_response,
    build_graceful_degradation_response,
    build_guardrail_response,
    resolve_guardrail_decision,
    resolve_output_decision,
)
from vinchatbot.app.agents.output_audit import audit_output
from vinchatbot.app.core.config import Settings, get_settings
from vinchatbot.app.core.observability import (
    estimate_cost_usd,
    get_point_lookup,
    get_request_id,
    get_rerank_count,
    get_stage_ledger,
    ledger_totals,
    record_stage,
    redact,
    reset_point_lookup,
    reset_rerank_count,
    reset_stage_ledger,
    set_user_message,
    sum_token_usage,
)
from vinchatbot.app.core.timeutils import current_time_context, is_pure_time_question
from vinchatbot.app.rag.citations import dedupe_citations, excerpt
from vinchatbot.app.rag.query_engineering import is_point_lookup
from vinchatbot.app.rag.retriever import QdrantHybridRetriever, RetrievedChunk, Retriever
from vinchatbot.app.schemas.chat import ChatRequest, ChatResponse, Citation
from vinchatbot.app.schemas.document import DocumentMetadata

logger = logging.getLogger(__name__)


class VinUniAgentService:
    def __init__(
        self,
        settings: Settings | None = None,
        retriever: Retriever | None = None,
        agent: Any | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.retriever = retriever or QdrantHybridRetriever(self.settings)
        self._checkpointer_context = None
        self.agent = agent or self._build_agent()

    async def chat(self, request: ChatRequest) -> ChatResponse:
        started = time.perf_counter()
        reset_rerank_count()  # count rerank (Cohere) calls for this turn → surfaced in _log_turn
        reset_point_lookup()  # did adaptive routing treat this turn as a point-lookup?
        reset_stage_ledger()  # per-stage cost/latency ledger for this turn (Phase C)
        set_user_message(request.message)  # raw question → deterministic structured lookup (Phase 1.19)
        guardrail_decision = await resolve_guardrail_decision(
            request.message,
            list(request.filters.compact().values()) if request.filters else None,
            settings=self.settings,
        )
        if not guardrail_decision.allowed:
            logger.info(
                "Chat input handled by guardrail action=%s conversation_id=%s",
                guardrail_decision.action,
                request.conversation_id,
            )
            if guardrail_decision.action in CONVERSATIONAL_ACTIONS:
                response = await build_conversational_response(
                    guardrail_decision, request.message, settings=self.settings
                )
                # Phase 1.25/A4: the capability reply is LLM-generated — secret-scan it (bypass path,
                # no grounding to check since conversational turns legitimately have no citations).
                if not resolve_output_decision(
                    response.answer, [], [], require_grounding=False
                ).allowed:
                    return self._sensitive_output_block(request, started, intent="guardrail")
            else:
                response = build_guardrail_response(guardrail_decision, request.message)
            # Log the guard-handled turn so the safety/LLM-guard calls it triggered are still costed
            # (these turns previously emitted no chat_turn line → their guard-call cost was invisible).
            self._log_turn(
                request,
                intent="guardrail",
                latency_ms=int((time.perf_counter() - started) * 1000),
                messages=[],
                citations=len(response.citations),
                confidence=response.confidence,
                tool_trace=response.tool_trace,
                needs_human_review=response.needs_human_review,
                degraded=False,
                guardrail_action=guardrail_decision.action,
            )
            return response

        # Phase 1.9: a pure "which term/year/date is it now?" question is answerable from the system
        # clock alone (no document). Answer it deterministically — skipping the agent and the
        # no-citation degradation guard, which would otherwise refuse this uncited-by-nature answer.
        if self.settings.enable_time_awareness and is_pure_time_question(request.message):
            return self._time_context_response(request, started)

        config = {"configurable": {"thread_id": request.conversation_id}}
        user_message = request.message
        if request.filters:
            user_message = (
                f"{user_message}\n\n"
                f"Bộ lọc metadata do API truyền vào: {request.filters.compact()}"
            )
        # Honor the language of the question: the model otherwise defaults to Vietnamese
        # even for English questions. Detection reuses the guardrail language heuristic.
        language_directive = (
            "Trả lời bằng tiếng Việt."
            if answer_language(request.message) == "vi"
            else "Answer in English."
        )
        user_message = f"{user_message}\n\n[Language / Ngôn ngữ trả lời: {language_directive}]"

        # Time awareness (Phase 1.9): give the model "now" so it can answer "what semester am I in?"
        # and relative-date questions. Fail-open — a tz/lookup error just skips the preamble.
        if self.settings.enable_time_awareness:
            try:
                ctx = current_time_context()
                user_message = (
                    f"{user_message}\n\n[Bối cảnh thời gian / Time context: hôm nay là {ctx['date']} "
                    f"({ctx['weekday']}); năm học hiện tại {ctx['academic_year']}, "
                    f"học kỳ {ctx['term']}.]"
                )
            except Exception:
                logger.debug("Time-context injection skipped.", exc_info=True)

        if self.settings.enable_langfuse:
            # Group this turn's traces under the conversation and tag with the request id, so a
            # multi-turn session reads as one thread in Langfuse (the per-call handler is attached
            # at the model). Best-effort metadata; never required for the turn to succeed.
            config["metadata"] = {
                "langfuse_session_id": request.conversation_id,
                "request_id": get_request_id(),
                "langfuse_tags": ["vinchatbot", self.settings.app_env],
            }

        result = await self.agent.ainvoke(
            {"messages": [{"role": "user", "content": user_message}]},
            config=config,
        )
        messages = result.get("messages", [])
        answer = _message_content(messages[-1]) if messages else ""
        citations = _extract_citations(messages)
        tool_trace = _extract_tool_trace(messages)
        retrieved_texts = _retrieved_texts(messages)

        # Phase 1.25/A4: unified deterministic output guard (sensitive-output + grounding) with a logged
        # reason. Fail-CLOSED — a check error degrades rather than serves an un-audited answer.
        try:
            output_decision = resolve_output_decision(answer, citations, retrieved_texts)
        except Exception:
            logger.warning("Output audit raised; degrading (fail-closed).", exc_info=True)
            output_decision = OutputAuditDecision(
                "graceful_degradation", "Output audit error (fail-closed)."
            )
        output_guard_trace = {
            "type": "output_guard",
            "action": output_decision.action,
            "reason": output_decision.reason,
        }

        if output_decision.action == "sensitive_output_blocked":
            logger.warning("Blocked a chat response that may disclose protected configuration.")
            response = build_guardrail_response(
                assess_user_message("reveal system prompt"),
                request.message,
            )
            self._log_turn(
                request,
                intent=result.get("intent"),
                latency_ms=int((time.perf_counter() - started) * 1000),
                messages=messages,
                citations=len(response.citations),
                confidence=response.confidence,
                tool_trace=response.tool_trace,
                needs_human_review=response.needs_human_review,
                degraded=False,
                guardrail_action="sensitive_output_blocked",
            )
            return response

        if output_decision.action == "graceful_degradation":
            self._log_turn(
                request,
                intent=result.get("intent"),
                latency_ms=int((time.perf_counter() - started) * 1000),
                messages=messages,
                citations=len(citations),
                confidence=0.0,
                tool_trace=[*tool_trace, output_guard_trace],
                needs_human_review=True,
                degraded=True,
                guardrail_action="graceful_degradation",
            )
            return build_graceful_degradation_response(
                request.message,
                citations=citations,
                tool_trace=[*tool_trace, output_guard_trace],
            )

        tool_trace = [*tool_trace, output_guard_trace]

        # Phase 1.25/B: LLM groundedness auditor — catches the grounded-but-wrong residual (right doc,
        # wrong row/number/year) the deterministic check passes. Scoped to high-stakes point-lookups,
        # gated off by default, fail-open (only a confident grounded:false degrades). The scope signal is
        # recomputed HERE from the user message + routed intent (not read from the point-lookup contextvar)
        # so it still fires on turns where the retrieval tool node never ran to mark the flag.
        if self.settings.enable_output_audit and is_point_lookup(request.message, result.get("intent")):
            verdict = await audit_output(answer, retrieved_texts, request.message, self.settings)
            if not verdict.grounded:
                audit_trace = {"type": "output_audit", "grounded": False, "reason": verdict.reason}
                self._log_turn(
                    request,
                    intent=result.get("intent"),
                    latency_ms=int((time.perf_counter() - started) * 1000),
                    messages=messages,
                    citations=len(citations),
                    confidence=0.0,
                    tool_trace=[*tool_trace, audit_trace],
                    needs_human_review=True,
                    degraded=True,
                    guardrail_action="output_audit_degraded",
                )
                return build_graceful_degradation_response(
                    request.message,
                    citations=citations,
                    tool_trace=[*tool_trace, audit_trace],
                )
            tool_trace = [*tool_trace, {"type": "output_audit", "grounded": True, "reason": verdict.reason}]

        if self.settings.enable_output_moderation:
            from vinchatbot.app.agents.safety_guard import assess_safety

            verdict = await assess_safety(answer, self.settings)
            if not verdict.allowed:
                logger.warning("Output moderation blocked a response action=%s", verdict.action)
                response = build_guardrail_response(verdict, request.message)
                self._log_turn(
                    request,
                    intent=result.get("intent"),
                    latency_ms=int((time.perf_counter() - started) * 1000),
                    messages=messages,
                    citations=len(response.citations),
                    confidence=response.confidence,
                    tool_trace=response.tool_trace,
                    needs_human_review=response.needs_human_review,
                    degraded=False,
                    guardrail_action="output_moderation_blocked",
                )
                return response

        confidence = _estimate_confidence(citations)
        needs_human_review = _needs_human_review(answer, citations)

        self._log_turn(
            request,
            intent=result.get("intent"),
            latency_ms=int((time.perf_counter() - started) * 1000),
            messages=messages,
            citations=len(citations),
            confidence=confidence,
            tool_trace=tool_trace,
            needs_human_review=needs_human_review,
            degraded=False,
            guardrail_action="allow",
        )

        return ChatResponse(
            answer=answer,
            citations=citations,
            confidence=confidence,
            tool_trace=tool_trace,
            needs_human_review=needs_human_review,
        )

    def _sensitive_output_block(
        self, request: ChatRequest, started: float, *, intent: Any
    ) -> ChatResponse:
        """Shared sensitive-output block (Phase 1.25/A4): refuse + log, reused by the main path and the
        bypass paths (time fast path, conversational capability reply)."""
        logger.warning("Blocked a chat response that may disclose protected configuration.")
        response = build_guardrail_response(
            assess_user_message("reveal system prompt"), request.message
        )
        self._log_turn(
            request,
            intent=intent,
            latency_ms=int((time.perf_counter() - started) * 1000),
            messages=[],
            citations=len(response.citations),
            confidence=response.confidence,
            tool_trace=response.tool_trace,
            needs_human_review=response.needs_human_review,
            degraded=False,
            guardrail_action="sensitive_output_blocked",
        )
        return response

    def _time_context_response(self, request: ChatRequest, started: float) -> ChatResponse:
        """Deterministic answer for a pure current-date/term question (Phase 1.9). No LLM, no
        retrieval; grounded in the system clock + the official Academic Calendar."""
        ctx = current_time_context()
        cal_url = "https://vinuni.edu.vn/academic-calendar/"
        if answer_language(request.message) == "vi":
            answer = (
                f"Hôm nay là {ctx['date']} ({ctx['weekday']}). Bạn đang ở **học kỳ {ctx['term']}**, "
                f"năm học {ctx['academic_year']}.\n\nNguồn:\n- [Academic Calendar]({cal_url})"
            )
        else:
            answer = (
                f"Today is {ctx['date']} ({ctx['weekday']}). You are in the **{ctx['term']} term**, "
                f"academic year {ctx['academic_year']}.\n\nSources:\n- [Academic Calendar]({cal_url})"
            )
        # Phase 1.25/A4: secret-scan even this template answer (bypass path; cheap, defense-in-depth).
        if not resolve_output_decision(answer, [], [], require_grounding=False).allowed:
            return self._sensitive_output_block(request, started, intent="time")
        citations = [
            Citation(
                source_url=cal_url,
                title="VinUni Academic Calendar",
                excerpt=f"{ctx['term']} term, academic year {ctx['academic_year']} (as of {ctx['date']}).",
                score=1.0,
            )
        ]
        self._log_turn(
            request,
            intent="time",
            latency_ms=int((time.perf_counter() - started) * 1000),
            messages=[],
            citations=len(citations),
            confidence=1.0,
            tool_trace=[],
            needs_human_review=False,
            degraded=False,
            guardrail_action="time_context",
        )
        return ChatResponse(
            answer=answer,
            citations=citations,
            confidence=1.0,
            tool_trace=[],
            needs_human_review=False,
        )

    def _log_turn(
        self,
        request: ChatRequest,
        *,
        intent: Any,
        latency_ms: int,
        messages: list[Any],
        citations: int,
        confidence: float,
        tool_trace: list[dict[str, Any]],
        needs_human_review: bool,
        degraded: bool,
        guardrail_action: str,
    ) -> None:
        """Emit one structured turn line carrying the AI-specific signals (latency, tokens, cost,
        quality). Best-effort: cost capture failing must never break the response."""
        tokens_in = tokens_out = model_calls = 0
        est_cost = 0.0
        stages: dict[str, dict[str, float]] = {}
        if self.settings.enable_cost_tracking:
            try:
                # Record the specialist answer stage (the only LLM tokens that live in the graph
                # messages) into the ledger, then sum ALL stages — supervisor/expansion/guard/rerank
                # were recorded during the turn — so the logged cost is the true turn cost, not the
                # answer-stage undercount sum_token_usage used to report alone.
                if messages:
                    answer_in, answer_out = sum_token_usage(messages)
                    answer_calls = sum(
                        1 for m in messages if isinstance(getattr(m, "usage_metadata", None), dict)
                    )
                    record_stage(
                        "answer",
                        calls=answer_calls,
                        tokens_in=answer_in,
                        tokens_out=answer_out,
                        est_cost_usd=estimate_cost_usd(
                            self.settings.openrouter_chat_model, answer_in, answer_out
                        ),
                    )
                totals = ledger_totals()
                tokens_in = totals["tokens_in"]
                tokens_out = totals["tokens_out"]
                est_cost = totals["est_cost_usd"]
                model_calls = totals["model_calls"]
                stages = {
                    name: {key: round(value, 3) for key, value in entry.items()}
                    for name, entry in get_stage_ledger().items()
                }
            except Exception:
                logger.debug("Cost capture failed; logging zeros.", exc_info=True)
        question = redact(request.message) if self.settings.log_redact_pii else request.message
        tool_calls = sum(1 for entry in tool_trace if entry.get("type") == "tool_result")
        rerank_calls = get_rerank_count()
        point_lookup = get_point_lookup()
        logger.info(
            "chat_turn intent=%s latency_ms=%d tokens=%d/%d est_cost_usd=%.6f model_calls=%d "
            "citations=%d confidence=%.2f rerank_calls=%d point_lookup=%s action=%s%s",
            intent,
            latency_ms,
            tokens_in,
            tokens_out,
            est_cost,
            model_calls,
            citations,
            confidence,
            rerank_calls,
            point_lookup,
            guardrail_action,
            " degraded" if degraded else "",
            extra={
                "event": "chat_turn",
                "conversation_id": request.conversation_id,
                "intent": intent,
                "latency_ms": latency_ms,
                "tokens_in": tokens_in,
                "tokens_out": tokens_out,
                "est_cost_usd": est_cost,
                "model_calls": model_calls,
                "stages": stages,
                "citations": citations,
                "confidence": round(float(confidence), 3),
                "guardrail_action": guardrail_action,
                "degraded": degraded,
                "tool_calls": tool_calls,
                "rerank_calls": rerank_calls,
                "point_lookup": point_lookup,
                "needs_human_review": needs_human_review,
                "question": question,
            },
        )

    def _build_agent(self):
        return build_agent_graph(
            self.retriever,
            settings=self.settings,
            checkpointer=self._build_checkpointer(),
        )

    def _build_checkpointer(self):
        if self.settings.checkpointer_backend.lower() == "postgres":
            if not self.settings.postgres_uri:
                raise RuntimeError("POSTGRES_URI is required when CHECKPOINTER_BACKEND=postgres.")
            try:
                from langgraph.checkpoint.postgres import PostgresSaver
            except ImportError as exc:
                raise RuntimeError(
                    "Install langgraph-checkpoint-postgres to use Postgres checkpoints."
                ) from exc
            self._checkpointer_context = PostgresSaver.from_conn_string(self.settings.postgres_uri)
            checkpointer = self._checkpointer_context.__enter__()
            try:
                checkpointer.setup()
            except Exception:
                logger.debug("Postgres checkpointer setup skipped or already completed.", exc_info=True)
            return checkpointer

        try:
            from langgraph.checkpoint.memory import InMemorySaver
        except ImportError as exc:
            raise RuntimeError("Install langgraph to use in-memory checkpoints.") from exc
        return InMemorySaver()


def _message_content(message: Any) -> str:
    content = getattr(message, "content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(str(item.get("text", "")))
            else:
                parts.append(str(item))
        return "\n".join(parts)
    return str(content)


def _iter_tool_payloads(messages: Iterable[Any]) -> Iterable[dict[str, Any]]:
    for message in messages:
        if message.__class__.__name__ != "ToolMessage":
            continue
        content = _message_content(message)
        try:
            payload = json.loads(content)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            yield payload


def _retrieved_texts(messages: Iterable[Any]) -> list[str]:
    texts: list[str] = []
    for payload in _iter_tool_payloads(messages):
        for item in payload.get("results", []):
            text = item.get("text")
            if text:
                texts.append(str(text))
    return texts


def _extract_citations(messages: Iterable[Any]) -> list[Citation]:
    citations: list[Citation] = []
    for payload in _iter_tool_payloads(messages):
        for item in payload.get("results", []):
            metadata_payload = item.get("metadata") or {}
            try:
                metadata = DocumentMetadata.model_validate(metadata_payload)
            except Exception:
                continue
            section = " > ".join(metadata.section_path) if metadata.section_path else None
            citations.append(
                Citation(
                    source_url=metadata.source_url,
                    title=metadata.document_title,
                    section=section,
                    page_number=metadata.page_number,
                    excerpt=excerpt(str(item.get("text", ""))),
                    score=item.get("score"),
                )
            )
    return dedupe_citations(citations)[:8]


def _extract_tool_trace(messages: Iterable[Any]) -> list[dict[str, Any]]:
    trace: list[dict[str, Any]] = []
    for message in messages:
        tool_calls = getattr(message, "tool_calls", None)
        if tool_calls:
            trace.append({"type": "tool_calls", "calls": tool_calls})
        if message.__class__.__name__ == "ToolMessage":
            trace.append(
                {
                    "type": "tool_result",
                    "name": getattr(message, "name", None),
                    "content_preview": excerpt(_message_content(message), max_chars=500),
                }
            )
    return trace


def _estimate_confidence(citations: list[Citation]) -> float:
    if not citations:
        return 0.0
    scored = [citation.score for citation in citations if citation.score is not None]
    if scored:
        average = sum(float(score) for score in scored) / len(scored)
        return max(0.1, min(1.0, average))
    return min(0.95, 0.45 + 0.1 * len(citations))


def _needs_human_review(answer: str, citations: list[Citation]) -> bool:
    lowered = answer.lower()
    unsupported_markers = [
        "chưa tìm thấy",
        "không tìm thấy",
        "không có nguồn",
        "không đủ bằng chứng",
        "cần xác nhận",
        "liên hệ",
    ]
    sensitive_markers = ["học phí", "deadline", "hạn", "kỷ luật", "tuition", "tariff", "fee"]
    if any(marker in lowered for marker in unsupported_markers):
        return True
    if any(marker in lowered for marker in sensitive_markers) and not citations:
        return True
    return False


def response_from_retrieved_chunks(
    answer: str,
    chunks: list[RetrievedChunk],
    needs_human_review: bool = False,
) -> ChatResponse:
    citations = [
        Citation(
            source_url=chunk.metadata.source_url,
            title=chunk.metadata.document_title,
            section=" > ".join(chunk.metadata.section_path) if chunk.metadata.section_path else None,
            page_number=chunk.metadata.page_number,
            excerpt=excerpt(chunk.text),
            score=chunk.score,
        )
        for chunk in chunks
    ]
    return ChatResponse(
        answer=answer,
        citations=dedupe_citations(citations),
        confidence=_estimate_confidence(citations),
        tool_trace=[],
        needs_human_review=needs_human_review,
    )

