from __future__ import annotations

from functools import lru_cache

from fastapi import APIRouter, HTTPException, status

from vinchatbot.app.agents.vinuni_agent import VinUniAgentService
from vinchatbot.app.schemas.chat import ChatRequest, ChatResponse

router = APIRouter(prefix="/chat", tags=["chat"])


@lru_cache
def get_agent_service() -> VinUniAgentService:
    return VinUniAgentService()


@router.post("", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    try:
        return await get_agent_service().chat(request)
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

