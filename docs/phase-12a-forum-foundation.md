# Phase 12A Forum Foundation

Phase 12A makes the student forum readable from the real FastAPI + Neon/Postgres app
database path. The frontend continues to call FastAPI only; it never connects directly
to Postgres.

## Database

Forum schema is provided by `migrations/000004_forum_schema.sql`:

- `forum_categories`
- `forum_topics`
- `forum_comments`
- Supporting tables already present for later phases: `forum_votes`, `forum_mentions`,
  and `forum_reports`

`migrations/000006_seed_forum_demo_data.sql` adds a small idempotent demo forum seed:

- Academic Q&A
- Campus Life
- Scholarships & Opportunities
- IT / Student Services

It inserts only safe demo forum categories, topics, and comments. It does not create
users, sessions, tokens, or secrets.

## Endpoints

Authenticated users can read:

- `GET /forum/categories`
- `GET /forum/topics`
- `GET /forum/topics/{topic_id}`
- `GET /forum/topics/{topic_id}/comments`

Anonymous users receive `401`. Missing topics return `404`. Empty forum state returns
empty arrays instead of `500`. If a deployed database is missing the forum migration,
forum routes still return a controlled `503` rather than exposing raw
`UndefinedTable` or `UndefinedColumn` errors.

## Frontend

The existing student forum page uses the real API through the Next proxy:

- `/student/forum` loads categories and topics.
- `/student/forum/topics/[id]` loads topic details and comments.
- Loading, error, and empty states use the existing async boundary components.

## Known Limitations

Phase 12A is the forum foundation. Complex moderation workflows, notification-to-forum
linking polish, richer institute visibility, and expanded posting/reply UX are left for
Phase 12B and later.

## Commands

Apply migrations against the Neon dev branch:

```bash
.venv/bin/python scripts/db_migrate.py
```

Run local verification:

```bash
.venv/bin/python -m ruff check .
.venv/bin/python -m pytest
(cd frontend && npm run typecheck)
```
