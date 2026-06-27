# Phase 9: Conversation Persistence APIs

Phase 9 adds authenticated backend APIs for listing, creating, reading,
renaming, and deleting user-owned conversations. It also adds a repository
foundation for safely appending messages to the existing `messages` table.

This phase does not change Qdrant retrieval, RAG ranking, OpenRouter model
selection, or existing `/chat` behavior.

## Authorization

All endpoints require a valid session token from `/auth/login`:

```http
Authorization: Bearer <token>
```

Example:

```bash
curl http://localhost:8000/conversations \
  -H "Authorization: Bearer <token>"
```

## Ownership Rules

Every conversation query is scoped by the authenticated `user_id`.

- Users can list only their own conversations.
- Users can read only their own conversation details and messages.
- Cross-user access returns `404` to avoid leaking whether a conversation exists.
- Responses do not include password hashes, session token hashes, or other auth
  secrets.

## Endpoints

- `GET /conversations`
  - Lists the current user's conversations, newest first.
- `POST /conversations`
  - Creates a conversation for the current user.
  - Optional body fields: `title`, `topic`, `initial_message`.
  - If `title` is missing and `initial_message` is present, a deterministic
    short title is derived from the first message.
- `GET /conversations/{conversation_id}`
  - Returns a conversation and its messages for the current user.
- `GET /conversations/{conversation_id}/messages`
  - Returns messages oldest first.
- `PATCH /conversations/{conversation_id}`
  - Updates `title`, `topic`, and optionally `title_manual`.
- `DELETE /conversations/{conversation_id}`
  - Deletes the current user's conversation. The current schema has no archive
    flag, so deletion is a guarded hard delete of the owned row. Message rows
    cascade through the existing foreign key.

Create example:

```bash
curl http://localhost:8000/conversations \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "initial_message": "When is the add/drop deadline?",
    "topic": "academic"
  }'
```

Rename example:

```bash
curl -X PATCH http://localhost:8000/conversations/<conversation_id> \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"title": "Academic deadline questions"}'
```

## Chat Persistence Status

`/chat` and `/chat/stream` still use the existing chat request contract and are
not persisted in this phase. The current chat schema already has a string
`conversation_id` used by the agent context, while the Postgres conversation
table uses UUID IDs. To avoid breaking existing clients or changing RAG/model
behavior, wiring chat turns into persisted conversations is deferred to Phase
9B.

Phase 9B should map authenticated chat requests to UUID conversations, save the
user message before model execution, save the final assistant response after
verification, and return the persisted `conversation_id` without changing
retrieval or model behavior.
