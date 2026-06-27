# Phase 5B: Demo Activity Seed

Phase 5B extends the demo seed script with synthetic student activity data.

```bash
python scripts/seed_demo_data.py --section activity --yes
```

To seed both academic data and activity data in one run:

```bash
python scripts/seed_demo_data.py --section all --yes
```

The activity section assumes the Phase 5A academic seed has already run. The
script uses `APP_DATABASE_URL_DIRECT`, refuses production environments, and does
not print database URLs or credentials.

## Seeded Activity

- Published notifications with all-student, institute, course, and cohort scopes
- Notification read state for selected demo accounts
- Campus and institute-specific events
- Student conversations and messages
- Support tickets with ticket messages and status history
- Anonymized student question events
- Aggregated question trends
- Suggested questions from trends, notifications, events, deadlines, and tickets

## Demo Nature

All data is synthetic and intended for development/demo use only. Conversation
messages are handcrafted examples; the seed script does not call LLMs, RAG,
Qdrant, OpenRouter, Redis, or any network service.

## Idempotency

The activity seed uses deterministic IDs and upserts. Running the command
multiple times updates the same demo-owned rows instead of duplicating them.

## Out of Scope

Phase 5B does not implement auth APIs, live chat persistence, frontend database
integration, or real production activity ingestion.
