# Phase 9B: Chat Persistence

Phase 9B persists authenticated `/chat` and `/chat/stream` turns into the app
Postgres `conversations` and `messages` tables without changing RAG retrieval,
agent routing, or OpenRouter model behavior.

## IDs

There are now two conversation identifiers in chat requests:

- `conversation_id`
  - Existing string field.
  - Still used by the agent/RAG context exactly as before.
  - Kept for backward compatibility.
- `db_conversation_id`
  - Optional UUID field.
  - Refers to `conversations.id` in Postgres.
  - Used only for authenticated database persistence.

## Optional Auth Behavior

Chat endpoints remain usable without authentication.

- Missing `Authorization` header: request runs anonymously and is not persisted.
- Malformed or invalid `Authorization` header: request is rejected.
- Valid bearer token: request can be persisted to the current user's
  conversation history.

Example authenticated request:

```bash
curl http://localhost:8000/chat \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "When is the add/drop deadline?",
    "conversation_id": "frontend-session-or-agent-context"
  }'
```

If no `db_conversation_id` is provided, the backend creates a new Postgres
conversation and returns its UUID:

```json
{
  "answer": "...",
  "citations": [],
  "confidence": 0.9,
  "tool_trace": [],
  "needs_human_review": false,
  "db_conversation_id": "11111111-1111-1111-1111-111111111111"
}
```

To continue persisting into the same DB conversation, send that UUID back:

```bash
curl http://localhost:8000/chat \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What should I do next?",
    "conversation_id": "frontend-session-or-agent-context",
    "db_conversation_id": "11111111-1111-1111-1111-111111111111"
  }'
```

## `/chat` Persistence

For authenticated requests:

1. The backend creates or validates the owned `db_conversation_id`.
2. The user message is appended before the agent/model call.
3. The current chat logic runs unchanged.
4. The assistant response is appended after the final response is produced.
5. The response includes `db_conversation_id` when persistence occurred.

If a provided `db_conversation_id` does not belong to the current user, the API
returns `404` before the model path runs. If persistence fails for an operational
reason, chat still returns normally and logs the persistence failure without
exposing connection details.

## `/chat/stream` Persistence

Streaming keeps the existing SSE protocol:

- `status`
- `delta`
- `done`
- `error`

For authenticated requests, persistence follows the same ownership rules as
`/chat`. The user message is saved before the stream starts. The assistant
message is saved from the accumulated final streamed content before the `done`
event is emitted. The `done` event includes `db_conversation_id` when
persistence occurred.

Unauthenticated streaming requests keep working without persistence.

## Security

- Users cannot persist messages into another user's conversation.
- Cross-user `db_conversation_id` access returns `404`.
- Chat responses do not include password hashes, session token hashes, database
  URLs, or other secrets.
