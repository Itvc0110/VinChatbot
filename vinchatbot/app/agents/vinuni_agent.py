from __future__ import annotations

import json
import logging
import time
from collections.abc import Iterable
from typing import Any

from vinchatbot.app.agents.graph import build_agent_graph
from vinchatbot.app.agents.guardrails import (
    CONVERSATIONAL_ACTIONS,
    answer_language,
    assess_faithfulness,
    assess_user_message,
    build_conversational_response,
    build_graceful_degradation_response,
    build_guardrail_response,
    contains_sensitive_output,
    resolve_guardrail_decision,
    should_gracefully_degrade,
)
from vinchatbot.app.core.config import Settings, get_settings
from vinchatbot.app.rag.citations import dedupe_citations, excerpt
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
                return await build_conversational_response(
                    guardrail_decision, request.message, settings=self.settings
                )
            return build_guardrail_response(guardrail_decision, request.message)

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

        result = await self.agent.ainvoke(
            {"messages": [{"role": "user", "content": user_message}]},
            config=config,
        )
        messages = result.get("messages", [])
        answer = _message_content(messages[-1]) if messages else ""
        citations = _extract_citations(messages)
        tool_trace = _extract_tool_trace(messages)
        retrieved_texts = _retrieved_texts(messages)

        if contains_sensitive_output(answer):
            logger.warning("Blocked a chat response that may disclose protected configuration.")
            return build_guardrail_response(
                assess_user_message("reveal system prompt"),
                request.message,
            )

        if should_gracefully_degrade(answer, citations) or not assess_faithfulness(
            answer, retrieved_texts
        ):
            logger.info(
                "Chat response used graceful degradation conversation_id=%s citations=%s",
                request.conversation_id,
                len(citations),
            )
            return build_graceful_degradation_response(
                request.message,
                citations=citations,
                tool_trace=tool_trace,
            )

        if self.settings.enable_output_moderation:
            from vinchatbot.app.agents.safety_guard import assess_safety

            verdict = await assess_safety(answer, self.settings)
            if not verdict.allowed:
                logger.warning("Output moderation blocked a response action=%s", verdict.action)
                return build_guardrail_response(verdict, request.message)

        confidence = _estimate_confidence(citations)
        needs_human_review = _needs_human_review(answer, citations)

        logger.info(
            "chat turn conversation_id=%s latency_ms=%d citations=%d confidence=%.2f",
            request.conversation_id,
            int((time.perf_counter() - started) * 1000),
            len(citations),
            confidence,
        )

        return ChatResponse(
            answer=answer,
            citations=citations,
            confidence=confidence,
            tool_trace=tool_trace,
            needs_human_review=needs_human_review,
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

