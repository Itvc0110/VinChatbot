from __future__ import annotations

import asyncio
import json
import logging
import re
import uuid
from dataclasses import dataclass
from functools import lru_cache
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from vinchatbot.app.agents.guardrails import (
    CONVERSATIONAL_ACTIONS,
    build_conversational_response,
    build_guardrail_response,
    resolve_guardrail_decision,
)
from vinchatbot.app.agents.vinuni_agent import VinUniAgentService
from vinchatbot.app.db.connection import get_app_db_pool
from vinchatbot.app.dependencies.auth import get_optional_current_user
from vinchatbot.app.repositories.auth import AuthenticatedUser
from vinchatbot.app.repositories.conversations import ConversationRepository
from vinchatbot.app.schemas.chat import ChatRequest, ChatResponse
from vinchatbot.app.schemas.conversations import AppendMessageRequest, CreateConversationRequest

router = APIRouter(prefix="/chat", tags=["chat"])
logger = logging.getLogger(__name__)


@lru_cache
def get_agent_service() -> VinUniAgentService:
    return VinUniAgentService()


@dataclass(frozen=True)
class ChatPersistenceContext:
    repository: ConversationRepository
    user_id: uuid.UUID
    conversation_id: uuid.UUID


async def get_optional_conversation_repository() -> ConversationRepository | None:
    pool = get_app_db_pool()
    return ConversationRepository(pool) if pool is not None else None


async def _resolve_chat(request: ChatRequest) -> ChatResponse:
    """Run guardrails + the agent and return the FINAL, safety-checked ChatResponse.

    Shared by the JSON endpoint and the streaming endpoint so both go through the
    identical faithfulness / moderation gates — the streamed answer is the verified
    one, never a raw generation that might later be retracted.
    """
    guardrail_decision = await resolve_guardrail_decision(
        request.message,
        list(request.filters.compact().values()) if request.filters else None,
    )
    if not guardrail_decision.allowed:
        logger.info(
            "Chat request handled before agent initialization action=%s conversation_id=%s",
            guardrail_decision.action,
            request.conversation_id,
        )
        if guardrail_decision.action in CONVERSATIONAL_ACTIONS:
            return await build_conversational_response(guardrail_decision, request.message)
        return build_guardrail_response(guardrail_decision, request.message)

    try:
        return await get_agent_service().chat(request)
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.exception("Chat request failed because an external service or agent step raised an error.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Chat service is temporarily unavailable. "
                f"Check the server log for {type(exc).__name__}."
            ),
        ) from exc


async def _prepare_chat_persistence(
    request: ChatRequest,
    current_user: AuthenticatedUser | None,
    repository: ConversationRepository | None,
) -> ChatPersistenceContext | None:
    if current_user is None:
        return None
    if repository is None:
        logger.warning("Skipping chat persistence because the app database pool is unavailable.")
        return None

    conversation_id = request.db_conversation_id
    if conversation_id is None:
        try:
            conversation = await repository.create_conversation(
                user_id=current_user.id,
                request=CreateConversationRequest(),
            )
            conversation_id = conversation["id"]
        except Exception:  # noqa: BLE001 - persistence must not break chat.
            logger.exception("Skipping chat persistence because conversation creation failed.")
            return None

    try:
        user_message = await repository.append_message(
            user_id=current_user.id,
            conversation_id=conversation_id,
            request=AppendMessageRequest(role="user", content=request.message),
        )
    except Exception:  # noqa: BLE001 - persistence must not break chat.
        logger.exception("Skipping chat persistence because user message append failed.")
        return None

    if user_message is None:
        if request.db_conversation_id is not None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found.",
            )
        logger.warning("Skipping chat persistence because the new conversation was not writable.")
        return None

    return ChatPersistenceContext(
        repository=repository,
        user_id=current_user.id,
        conversation_id=conversation_id,
    )


async def _persist_assistant_response(
    persistence: ChatPersistenceContext | None,
    response: ChatResponse,
    *,
    assistant_content: str | None = None,
) -> None:
    if persistence is None:
        return

    response.db_conversation_id = persistence.conversation_id
    content = assistant_content if assistant_content is not None else response.answer
    if not content:
        return

    try:
        await persistence.repository.append_message(
            user_id=persistence.user_id,
            conversation_id=persistence.conversation_id,
            request=AppendMessageRequest(
                role="assistant",
                content=content,
                answer_json=response.model_dump(mode="json"),
                confidence=response.confidence,
                needs_human_review=response.needs_human_review,
            ),
        )
    except Exception:  # noqa: BLE001 - persistence must not break chat.
        logger.exception("Assistant response persistence failed.")


@router.post("", response_model=ChatResponse, response_model_exclude_none=True)
async def chat(
    request: ChatRequest,
    current_user: Annotated[
        AuthenticatedUser | None,
        Depends(get_optional_current_user),
    ] = None,
    conversation_repository: Annotated[
        ConversationRepository | None,
        Depends(get_optional_conversation_repository),
    ] = None,
) -> ChatResponse:
    persistence = await _prepare_chat_persistence(
        request,
        current_user,
        conversation_repository,
    )
    response = await _resolve_chat(request)
    await _persist_assistant_response(persistence, response)
    return response


# Split on word boundaries but KEEP the whitespace, so reassembling the deltas on the
# client reproduces the answer exactly (markdown links, newlines, code all intact).
_CHUNK_RE = re.compile(r"\S+\s*")


def _answer_chunks(answer: str, group: int = 4) -> list[str]:
    tokens = _CHUNK_RE.findall(answer)
    return ["".join(tokens[i : i + group]) for i in range(0, len(tokens), group)]


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


# How often to emit an SSE heartbeat while the (slow) verify-then-reveal compute runs, so
# the proxy/client connection never sits idle long enough to be reset (socket hang up).
_HEARTBEAT_SECONDS = 10.0


@router.post("/stream")
async def chat_stream(
    request: ChatRequest,
    current_user: Annotated[
        AuthenticatedUser | None,
        Depends(get_optional_current_user),
    ] = None,
    conversation_repository: Annotated[
        ConversationRepository | None,
        Depends(get_optional_conversation_repository),
    ] = None,
) -> StreamingResponse:
    """Verify-then-reveal streaming.

    The full answer is computed and passed through every safety gate FIRST (so we never
    stream a token we might have to retract); only then is the approved answer revealed
    token-by-token over SSE, followed by a final `done` event carrying citations + meta.

    The compute runs INSIDE the generator so the HTTP response (headers + first byte) opens
    immediately and a heartbeat comment is flushed every few seconds while the agent works.
    Without this the endpoint sent nothing for the whole ~30s compute and the proxy reset the
    idle connection; the client then fell back to /chat and re-ran the entire agent. A failure
    during compute surfaces as an `error` SSE event (the response has already started, so a
    plain HTTP 503 is no longer possible).
    """

    persistence = await _prepare_chat_persistence(
        request,
        current_user,
        conversation_repository,
    )

    async def event_stream():
        # First yield flushes the 200 + SSE headers right away and tells the client the stream
        # has opened (so a later failure is reported as an `error` event, NOT retried as a fresh
        # /chat run). An empty step keeps the client on its own localized "Searching…" placeholder.
        yield _sse("status", {"step": ""})

        task = asyncio.create_task(_resolve_chat(request))
        try:
            # Heartbeat until the verified answer is ready (or the compute fails).
            while True:
                done, _ = await asyncio.wait({task}, timeout=_HEARTBEAT_SECONDS)
                if done:
                    break
                yield ": keepalive\n\n"

            try:
                response = task.result()
            except HTTPException as exc:
                yield _sse("error", {"detail": exc.detail})
                return
            except Exception as exc:  # noqa: BLE001 — surface as a stream error, not a 500.
                logger.exception("Streaming chat failed during compute.")
                yield _sse(
                    "error",
                    {"detail": f"Chat service is temporarily unavailable ({type(exc).__name__})."},
                )
                return

            if persistence is not None:
                response.db_conversation_id = persistence.conversation_id

            assistant_chunks: list[str] = []
            for chunk in _answer_chunks(response.answer):
                assistant_chunks.append(chunk)
                yield _sse("delta", {"text": chunk})
                await asyncio.sleep(0.014)  # gentle typewriter cadence
            await _persist_assistant_response(
                persistence,
                response,
                assistant_content="".join(assistant_chunks),
            )
            yield _sse("done", response.model_dump(mode="json", exclude_none=True))
        finally:
            # Client disconnected / pressed Stop, or we finished — make sure an in-flight agent
            # run doesn't keep computing (and spending) into a dead socket.
            if not task.done():
                task.cancel()

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",  # disable proxy buffering so deltas flush live
            "Connection": "keep-alive",
        },
    )
