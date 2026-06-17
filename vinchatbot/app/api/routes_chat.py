from __future__ import annotations

import asyncio
import json
import logging
import re
from functools import lru_cache

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse

from vinchatbot.app.agents.guardrails import (
    CONVERSATIONAL_ACTIONS,
    build_conversational_response,
    build_guardrail_response,
    resolve_guardrail_decision,
)
from vinchatbot.app.agents.vinuni_agent import VinUniAgentService
from vinchatbot.app.schemas.chat import ChatRequest, ChatResponse

router = APIRouter(prefix="/chat", tags=["chat"])
logger = logging.getLogger(__name__)


@lru_cache
def get_agent_service() -> VinUniAgentService:
    return VinUniAgentService()


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


@router.post("", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    return await _resolve_chat(request)


# Split on word boundaries but KEEP the whitespace, so reassembling the deltas on the
# client reproduces the answer exactly (markdown links, newlines, code all intact).
_CHUNK_RE = re.compile(r"\S+\s*")


def _answer_chunks(answer: str, group: int = 4) -> list[str]:
    tokens = _CHUNK_RE.findall(answer)
    return ["".join(tokens[i : i + group]) for i in range(0, len(tokens), group)]


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/stream")
async def chat_stream(request: ChatRequest) -> StreamingResponse:
    """Verify-then-reveal streaming.

    The full answer is computed and passed through every safety gate FIRST (so we never
    stream a token we might have to retract); only then is the approved answer revealed
    token-by-token over SSE, followed by a final `done` event carrying citations + meta.
    Errors before the stream starts surface as normal HTTP 503; this matches /chat.
    """
    response = await _resolve_chat(request)

    async def event_stream():
        try:
            for chunk in _answer_chunks(response.answer):
                yield _sse("delta", {"text": chunk})
                await asyncio.sleep(0.014)  # gentle typewriter cadence
            yield _sse("done", response.model_dump())
        except asyncio.CancelledError:
            # Client disconnected / pressed Stop — end quietly.
            raise

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",  # disable proxy buffering so deltas flush live
            "Connection": "keep-alive",
        },
    )
