# Phase 12C: Forum UX, Discovery, Notifications, and Vinnie Integration

## Summary

Phase 12C turns the Forum module into a more demo-ready discussion experience and connects forum activity to the existing notification and suggested-question workflows.

The implementation keeps FastAPI as the only structured-data access layer. The frontend continues to call the Next `/api/*` proxy, and no frontend code connects directly to Neon/Postgres.

## UX Improvements

- Forum topic list now supports URL-backed filters for category, search, sort, and moderator-only status visibility.
- Topic cards show clearer state badges for pinned, locked, archived, official answer, and admin/staff authors.
- Topic detail treats locked and archived topics as read-only for normal posting/editing flows.
- Comment threads show author/staff badges and a clean hidden-comment placeholder for students.
- Moderators can still see hidden comment content and unhide it.
- Create-topic and reply flows retain mention support and avoid exposing raw API errors in the UI.
- Forum state is refetched and local page/form state is cleared when auth token/user identity changes.

## Discovery Behavior

`GET /forum/topics` now supports:

- `category` for category slug filtering.
- `category_id` for category UUID filtering.
- `q` or `search` for title/body search.
- `sort=pinned`, `sort=newest_activity`, or `sort=most_commented`.
- Existing sort aliases `active`, `new`, and `top` remain compatible.
- `status=active|archived|all` for moderators.

Pinned topics are ordered first in all primary sort modes. Archived topics remain hidden from normal student lists.

## Notifications

Moderators now have a focused action:

- `POST /forum/topics/{topic_id}/notification`

The endpoint creates a `forum` notification linked by `forum_topic_id`. Global admins default to all-student targeting. Institute-scoped admins/staff default to their allowed institute target when it can be resolved, and the existing admin notification repository enforces scope.

Student notification responses already carry `forum_topic_id`/`forum_comment_id`, and the frontend maps those to an in-app forum topic action.

## Vinnie Suggestions

`/suggestions/me` now includes deterministic forum-topic suggestions from visible active topics. The rule engine:

- Uses pinned/recent topics.
- Excludes archived/deleted topics.
- Filters student-authored topics to the current student institute; staff/admin-authored topics are treated as globally relevant.
- Emits `source_type: "forum_topic"` and the topic UUID as `source_id`.
- Uses rule-based templates only, with no LLM calls.

Frontend dashboard and chat welcome suggestions still submit the suggested question normally. Forum-driven suggestions also show a small related topic link where that context is available.

## Permissions And Moderation

- Students cannot reply to locked or archived topics.
- Students cannot see archived topics in normal lists.
- Students see hidden comments as a clean placeholder.
- Admin/staff can list archived topics using the status filter and can see hidden comment content for moderation.
- Author edit/delete actions disappear on locked or archived topics.
- Notification targeting stays within existing all-student or institute-scoped notification permissions.

## Known Limitations

- Forum topics do not yet have an explicit target audience column; suggestion institute scoping is inferred from the topic author's student profile where available.
- “Create notification from topic” uses a simple default title/message. It does not yet provide a full audience/preview form in the forum UI.
- Normal comments do not create broad notifications by default; only existing mention/reply notifications and the explicit moderator action do.

## Verification

Completed during implementation:

- `.venv/bin/python -m ruff check .` passed.
- `.venv/bin/python -m pytest` passed: 534 passed, 1 skipped.
- `(cd frontend && npm run typecheck)` passed.
- Docker build/start smoke passed with `docker compose down` and `docker compose up --build -d`.
- Inside-container probes passed:
  - Backend `GET /health` returned 200.
  - Frontend `GET /login` returned 200.

Not completed in this run:

- `.venv/bin/python scripts/db_migrate.py` was not run because the approval reviewer blocked mutating the configured database.
- Browser login and create/comment/moderation smoke actions were not performed because they would mutate the same configured database without explicit approval for that database.
- Host-level `curl localhost:{80,3000,8000}` probes failed from the tool sandbox even while Compose showed the services running; inside-container probes succeeded.
- Caddy started, but its logs showed ACME challenge failures for the configured domain. Backend and frontend services were still reachable from inside their containers.
