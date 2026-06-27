# Phase 10C: Chat History Integration

Phase 10C connects the student chat UI to the authenticated backend
conversation APIs from Phase 9A/9B while preserving the existing streaming chat
experience.

## APIs Integrated

- `GET /conversations`
- `POST /conversations`
- `GET /conversations/{conversation_id}`
- `GET /conversations/{conversation_id}/messages`
- `PATCH /conversations/{conversation_id}`
- `DELETE /conversations/{conversation_id}`
- `POST /chat`
- `POST /chat/stream`

The browser reaches these through Next rewrites:

- `/api/conversations/*`
- `/api/chat`
- `/api/chat/stream`

All authenticated requests use the Phase 10A bearer-token helper.

## Conversation IDs

The frontend keeps two conversation identifiers separate:

- `conversation_id` is the legacy string thread id used by the RAG/agent path
  for chat context.
- `db_conversation_id` is the Postgres UUID used by the app database for
  persisted conversation history and messages.

When a persisted conversation is selected, chat requests send both IDs. For a
new empty chat, the frontend sends only the legacy thread id; the backend may
create a database conversation and return `db_conversation_id`, which the UI
then adopts.

## Refresh Behavior

On student-shell load, the chat provider fetches `GET /conversations` and shows
the backend conversation history in the existing conversation rail. Selecting a
conversation lazily fetches `GET /conversations/{id}/messages`, then renders the
persisted `user` and `assistant` messages.

Stored user messages may include the frontend personalization prefix that was
sent to the chat endpoint. The UI displays the original question after the
`Question:` marker so refreshed chats remain readable.

## Current Behavior

- New chat starts as an empty local draft and is persisted on first message.
- Local drafts and locally sent conversations are kept at the top of the rail
  immediately; refreshed backend history is ordered by `last_message_at`, then
  `updated_at`, then `created_at`.
- Sending a message uses `/chat/stream` first, then the existing non-streaming
  fallback if the stream never opens.
- Rename calls `PATCH /conversations/{id}` for persisted conversations.
- Delete calls `DELETE /conversations/{id}` for persisted conversations.
- Suggested-question clicks continue through the normal active chat flow.

## Known Limitations

- Existing database conversations do not store the old agent thread id, so the
  frontend derives a stable `db-{uuid}` thread id for future turns in that
  conversation.
- Chat title generation remains deterministic in the frontend and does not call
  an LLM.
- Ticket and chat-history cross-linking in the ticket UI is handled in a later
  frontend phase.
