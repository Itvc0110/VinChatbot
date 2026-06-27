# Phase 14A: Backend-owned Vinnie personalization context

## Summary

Phase 14A moves chat personalization out of the browser and into the backend. Previously the
frontend prepended a hidden block of profile/schedule/deadline/tuition text to every question, so
the *visible* question and the *persisted* user message diverged: chat history stored an expanded
prompt rather than what the student actually typed, and the personalization payload was assembled
client-side from data the client happened to have cached.

Now the chat route builds a bounded, current-student-only context **server-side** from
Neon/Postgres and attaches it to the agent input. The frontend sends only the raw question, and
chat persistence stores that raw question. FastAPI remains the only structured-data access layer.

## Backend-owned personalization context

`PersonalizationRepository` (`vinchatbot/app/repositories/personalization.py`) gathers a bounded
snapshot of the **current authenticated student's own** data and returns a `PersonalizationContext`
(`vinchatbot/app/schemas/personalization.py`):

- Profile + institute + program + academic summary (GPA, credits, standing, current semester).
- Current courses / enrollments.
- Next few upcoming schedule items.
- Next few upcoming deadlines.
- Active, visible notifications.
- Top smart suggestions.
- Recent visible forum topics.
- Recent conversation metadata.

It reuses the existing `StudentRepository` read paths (which already enforce student scoping and
notification visibility) and adds two scoped queries for forum topics and recent conversations.

### Limits and exclusions

- Strict per-source caps: courses 5, schedule 5, deadlines 5, notifications 5, suggestions 6,
  forum topics 4, conversations 3.
- Other students' data is excluded — every query is keyed by the current user's id / profile id.
- Hidden/archived/future-invisible content is excluded:
  - Notifications come from `StudentRepository.get_notifications`, which already filters to
    `status in ('published','scheduled')` and the active `start_date`/`end_date` window; archived
    notifications are then dropped during ranking.
  - Forum topics are filtered to `deleted = false` and active categories, and scoped to the
    student's institute (plus institute-agnostic authors).
- Admin-only / private notes are never selected (advisor notes, internal fields, password/token
  hashes are not part of any selected column set).

## Optional context endpoint

`GET /personalization/me/context` (`vinchatbot/app/api/routes_personalization.py`, wired in
`main.py`):

- Anonymous callers → **401** (no bearer token).
- Non-student roles (admin/staff) → **403** via `require_roles("student")`; the repository is never
  consulted.
- Students → their own `PersonalizationContext`.
- A student with no profile row → **404**.

This mirrors the existing `/students/me*` and `/suggestions/me` patterns.

## Chat integration

`vinchatbot/app/api/routes_chat.py`:

- A new optional dependency, `get_optional_personalization_repository`, returns a
  `PersonalizationRepository` when the app DB pool is available.
- `_attach_personalization(request, current_user, repository)` runs in both `/chat` and
  `/chat/stream` **before** `_resolve_chat`:
  - It always clears `request.backend_personalization_context` first, so a client can never smuggle
    in a fabricated context.
  - Only an authenticated **student** with `ai_personalization_enabled` receives a context;
    anonymous and admin/staff turns leave the field `None`.
  - Failures are swallowed and logged — personalization never breaks chat.
- The context is rendered to a bounded plain-text block by `build_personalization_prompt`, capped at
  `MAX_PROMPT_CHARS` (6000), matching the `ChatRequest.backend_personalization_context` field bound.

`vinchatbot/app/agents/vinuni_agent.py` reads `request.backend_personalization_context` and appends
it to the model input as advisory background (the agent still grounds facts in retrieval). This is
the only change to the agent path; the async supervisor routing and the graph itself are untouched.

### What is persisted

- The **original** user question (`request.message`) is what gets appended to chat history — never
  the expanded personalization block.
- `backend_personalization_context` is a `ChatRequest` field declared with `exclude=True`, so it is
  never serialized into any `model_dump`, response, or persisted message.
- Existing `conversation_id` / `db_conversation_id` behavior and Phase 10C persistence are
  unchanged.

## Frontend cleanup

`frontend/lib/chat.tsx`:

- Removed `buildPersonalContext()` and the hidden prepended block. The chat request now sends
  `message: text` — the actual user question only.
- Removed the `personalData` ref and the effect that pre-fetched profile/schedule/deadlines/tuition
  purely to build that block (and the now-unused imports/helpers).
- Visible UX is unchanged: answers are still marked personalized, suggestions, dashboard, chat, and
  widget all keep working. Because the frontend no longer carries any personalization payload,
  account switching cannot leak stale personalization context — the backend derives it fresh per
  request from the authenticated session.

## Tests

- `tests/test_personalization_api.py`
  - Anonymous `GET /personalization/me/context` → 401.
  - Admin → 403 and the repository is never called.
  - Student → their own bounded context (profile/courses/schedule/deadlines/notifications/
    suggestions/forum/conversations present), fetched for that student's id only.
  - Student with no profile → 404.
  - `build_personalization_prompt` includes each source and stays within the 6000-char bound.
  - Repository unit tests (with a fake `StudentRepository`, no DB): every source is scoped to the
    current student's id, per-source limits are applied, and archived notifications are excluded.
- `tests/test_chat_personalization.py`
  - Authenticated student `/chat` and `/chat/stream` build and attach the context; the raw question
    reaches the agent and is persisted (no expanded prompt in history).
  - Anonymous `/chat` attaches no personalization and still works.
  - Admin `/chat` never triggers a student-context lookup.
  - Client-supplied `backend_personalization_context` is cleared for non-students.
  - A student with `ai_personalization_enabled = false` gets no context.
- No test depends on a live LLM call (`_resolve_chat` is stubbed).

## Verification

- `.venv/bin/python -m ruff check .` → passed.
- `.venv/bin/python -m pytest` → 554 passed, 1 skipped.
- `(cd frontend && npm run typecheck)` → passed.

## Hotfix: trusted app-data acceptance in the output guard

The initial Phase 14A build attached the context correctly, but the deterministic output guard still
required RAG/official citations for *every* answer, so personal app-data questions
("Có thông báo nào quan trọng không?") were degraded to the official-source fallback despite a
populated context.

The hotfix adds a narrow, opt-in trusted path:

- **`vinchatbot/app/agents/question_scope.py`** — a rule-based (no-LLM) `classify_question_scope()`
  returning `personal_app_data`, `official_policy`, `hybrid`, or `general_unknown`. It matches
  Vietnamese/English personal pronouns, app-data nouns, and policy terms (accent-insensitive, via
  `normalize_for_matching`). Inherently-personal nouns (notification/schedule/deadline/GPA/credits/
  forum/ticket) count as personal even without a pronoun; generic nouns (course/class) need a
  pronoun; any policy term with a personal angle → `hybrid`.
- **`resolve_output_decision(..., trusted_app_data=False)`** — when `True`, the citation-presence
  and numeric-grounding checks are skipped; only the secret scan and an explicit
  unknown-answer/decline marker still degrade. The RAG requirement is **not** relaxed globally.
- **`vinuni_agent.py`** — computes `scope` once and sets
  `trusted_app_data = bool(backend_personalization_context) and scope == "personal_app_data"`. This
  is derived **only** from the server-built context, never from client input. The flag is passed to
  the output guard and also skips the LLM groundedness/intent audit (which checks retrieved
  evidence, irrelevant to context-grounded answers). The injected context block is scope-aware:
  for `personal_app_data`/`hybrid` it tells the model the context is trusted current-student data it
  may answer from directly (summarizing notifications with title/priority/deadline) without official
  citations, while any policy claim still needs retrieved official sources.

Scope behavior:

- `personal_app_data` + server context → answered from trusted context, no citations required.
- `official_policy` → unchanged; still requires RAG/official citations (uncited → degrade).
- `hybrid` → no trusted bypass, so policy claims still require citations; the prompt instructs the
  model to answer the personal part from context and say the official rule needs confirmation.
- `general_unknown` → unchanged.

### Hotfix tests

- `tests/test_question_scope.py` — classifier scope cases (VI + EN).
- `tests/test_guardrails.py` — `trusted_app_data` allows an uncited app-data answer, still blocks
  secrets, still degrades on a decline marker; policy answers without citations still degrade.
- `tests/test_chat_personalization.py` — agent-level (real output guard, fake agent, offline):
  a personal app-data answer is served uncited; an official-policy answer without citations
  degrades; a hybrid policy claim without citations degrades.

### Hotfix verification

- `ruff check .` → passed.
- `pytest` → 579 passed, 1 skipped.
- `(cd frontend && npm run typecheck)` → passed.
- Docker smoke (`docker compose up --build -d`, logged in as `student.cs.demo@vinuni.edu.vn`):
  "Có thông báo nào quan trọng không?", "Tôi có deadline nào sắp tới?", and "Hôm nay tôi có lịch
  gì?" are answered from backend context (guard `allow`, 0 citations, no degradation). Official
  policy questions answer with RAG citations; anonymous chat answers from RAG with citations and no
  personalization; the persisted user message is the raw question (no hidden block).

## Known limitations

- Notification/forum visibility relies on the existing SQL filters (status, date window,
  `deleted`/`is_active`); the unit tests assert archived exclusion and scoping directly, while the
  date-window/status filtering is covered at the SQL layer rather than against a live database.
- The rendered context is advisory text; the agent decides whether and how to use it, and continues
  to ground factual claims in retrieved sources.
- Personalization requires the app DB pool; when it is unavailable the chat path degrades to
  non-personalized answers (logged, never fatal).
