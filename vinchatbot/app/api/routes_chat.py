from __future__ import annotations

import logging
from functools import lru_cache

from fastapi import APIRouter, HTTPException, status

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


@router.post("", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
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

