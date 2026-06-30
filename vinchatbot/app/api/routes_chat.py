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

from vinchatbot.app.agents.vinuni_agent import VinUniAgentService
from vinchatbot.app.core.observability import reset_student_identity, set_student_identity
from vinchatbot.app.db.connection import get_app_db_pool
from vinchatbot.app.dependencies.auth import get_chat_user
from vinchatbot.app.repositories.auth import AuthenticatedUser
from vinchatbot.app.repositories.conversations import ConversationRepository
from vinchatbot.app.repositories.personalization import (
    PersonalizationRepository,
    build_personalization_prompt,
)
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


async def get_optional_personalization_repository() -> PersonalizationRepository | None:
    pool = get_app_db_pool()
    return PersonalizationRepository(pool) if pool is not None else None


async def _attach_personalization(
    request: ChatRequest,
    current_user: AuthenticatedUser | None,
    repository: PersonalizationRepository | None,
) -> None:
    """Build the current student's context server-side and attach it to the request.

    Always clears any client-supplied value first so a caller can never inject a fabricated
    personalization block. Only authenticated students with AI personalization enabled receive a
    context; anonymous and admin/staff turns leave the field None. Failures are swallowed so
    personalization never breaks chat.
    """
    request.backend_personalization_context = None
    if current_user is None or repository is None:
        return
    if "student" not in current_user.roles:
        return

    try:
        context = await repository.get_context(current_user.id)
    except Exception:  # noqa: BLE001 - personalization must not break chat.
        logger.exception("Skipping chat personalization because context lookup failed.")
        return

    if context is None or not context.profile.ai_personalization_enabled:
        return

    prompt = build_personalization_prompt(context)
    if prompt:
        request.backend_personalization_context = prompt


def _bind_student_identity(current_user: AuthenticatedUser | None):
    """Bind the VERIFIED student's identity for this turn so the read-only personal DB tools can
    hard-scope every query to this student's own rows.

    Security core: the id is taken ONLY from the authenticated session (current_user), never from the
    request body or the model. Returns a reset token to clear in a finally block, or None for
    anonymous / admin / profile-less turns (the personal tools then refuse). Must be called in the
    same context that runs / spawns the agent so child tool tasks inherit the binding.
    """
    if current_user is None or "student" not in current_user.roles:
        return None
    profile = current_user.student_profile
    if not profile or not profile.get("id"):
        return None
    return set_student_identity(student_profile_id=profile["id"], user_id=current_user.id)


async def _resolve_chat(request: ChatRequest) -> ChatResponse:
    """Run the agent and return the FINAL, safety-checked ChatResponse.

    Shared by the JSON endpoint and the streaming endpoint so both go through the
    identical faithfulness / moderation gates — the streamed answer is the verified
    one, never a raw generation that might later be retracted.

    Guardrails run ONCE, inside ``VinUniAgentService.chat`` (which builds the conversational /
    guardrail responses AND logs the guard-handled turn). The earlier duplicate pre-call here was
    removed to avoid double guard cost/latency per turn.
    """
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
        Depends(get_chat_user),
    ] = None,
    conversation_repository: Annotated[
        ConversationRepository | None,
        Depends(get_optional_conversation_repository),
    ] = None,
    personalization_repository: Annotated[
        PersonalizationRepository | None,
        Depends(get_optional_personalization_repository),
    ] = None,
) -> ChatResponse:
    persistence = await _prepare_chat_persistence(
        request,
        current_user,
        conversation_repository,
    )
    await _attach_personalization(request, current_user, personalization_repository)
    identity_token = _bind_student_identity(current_user)
    try:
        response = await _resolve_chat(request)
    finally:
        reset_student_identity(identity_token)
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
        Depends(get_chat_user),
    ] = None,
    conversation_repository: Annotated[
        ConversationRepository | None,
        Depends(get_optional_conversation_repository),
    ] = None,
    personalization_repository: Annotated[
        PersonalizationRepository | None,
        Depends(get_optional_personalization_repository),
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
    await _attach_personalization(request, current_user, personalization_repository)

    async def event_stream():
        # First yield flushes the 200 + SSE headers right away and tells the client the stream
        # has opened (so a later failure is reported as an `error` event, NOT retried as a fresh
        # /chat run). An empty step keeps the client on its own localized "Searching…" placeholder.
        yield _sse("status", {"step": ""})

        identity_token = None
        task = None
        try:
            # Bind the student identity HERE (in the generator's context) before create_task, so the
            # task that runs the agent + personal tools inherits the binding (contextvars copy at task
            # creation). Inside the try so the finally always resets it, even on an unexpected raise.
            identity_token = _bind_student_identity(current_user)
            task = asyncio.create_task(_resolve_chat(request))
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
            if task is not None and not task.done():
                task.cancel()
            reset_student_identity(identity_token)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",  # disable proxy buffering so deltas flush live
            "Connection": "keep-alive",
        },
    )
