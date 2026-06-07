from __future__ import annotations

import json
import logging
from collections.abc import Iterable
from typing import Any

from vinchatbot.app.agents.tools import build_retrieval_tools
from vinchatbot.app.core.config import Settings, get_settings
from vinchatbot.app.llm.openrouter_chat import build_chat_model
from vinchatbot.app.rag.citations import dedupe_citations, excerpt
from vinchatbot.app.rag.retriever import QdrantHybridRetriever, RetrievedChunk, Retriever
from vinchatbot.app.schemas.chat import ChatRequest, ChatResponse, Citation
from vinchatbot.app.schemas.document import DocumentMetadata

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """Bạn là VinChatbot, trợ lý hỗ trợ sinh viên VinUni.

Ngôn ngữ mặc định là tiếng Việt. Nếu người dùng hỏi bằng ngôn ngữ khác, có thể trả lời cùng ngôn ngữ đó.

Nguyên tắc bắt buộc:
- Dùng ReAct: suy nghĩ ngắn gọn về loại câu hỏi, gọi tool retrieval phù hợp, quan sát kết quả, rồi mới trả lời.
- Không dùng lịch sử hội thoại làm nguồn sự thật cho học phí, deadline, quy định, quyền lợi hoặc nghĩa vụ.
- Mọi claim quan trọng về chính sách, học phí, mốc thời gian phải dựa trên kết quả tool và có citation.
- Nếu kết quả tool không đủ bằng chứng, nói rõ là chưa tìm thấy nguồn chính thức trong dữ liệu hiện có.
- Không truy cập hoặc suy đoán dữ liệu riêng tư từ SIS, Canvas, email, tài khoản cá nhân hoặc trang cần đăng nhập.
- Câu trả lời nên ngắn, thực dụng, có phần "Nguồn" khi có citation.
"""


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
        config = {"configurable": {"thread_id": request.conversation_id}}
        user_message = request.message
        if request.filters:
            user_message = (
                f"{request.message}\n\n"
                f"Bộ lọc metadata do API truyền vào: {request.filters.compact()}"
            )

        result = await self.agent.ainvoke(
            {"messages": [{"role": "user", "content": user_message}]},
            config=config,
        )
        messages = result.get("messages", [])
        answer = _message_content(messages[-1]) if messages else ""
        citations = _extract_citations(messages)
        confidence = _estimate_confidence(citations)
        needs_human_review = _needs_human_review(answer, citations)

        if not citations and not needs_human_review:
            needs_human_review = True
            answer = (
                answer.strip()
                or "Mình chưa tìm thấy nguồn chính thức đủ mạnh trong dữ liệu hiện có để trả lời chắc chắn."
            )

        return ChatResponse(
            answer=answer,
            citations=citations,
            confidence=confidence,
            tool_trace=_extract_tool_trace(messages),
            needs_human_review=needs_human_review,
        )

    def _build_agent(self):
        try:
            from langchain.agents import create_agent
        except ImportError as exc:
            raise RuntimeError("Install langchain to create the VinUni ReAct agent.") from exc

        return create_agent(
            model=build_chat_model(self.settings),
            tools=build_retrieval_tools(self.retriever),
            system_prompt=SYSTEM_PROMPT,
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

