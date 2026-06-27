# Phase 3: Initial App Schema

Phase 3 adds the first Student Copilot application schema through:

```bash
python scripts/db_migrate.py
```

Run this migration only against the Neon `dev` branch for now. Do not apply it to a
production branch until auth, data-retention, seed, and rollback plans are ready.

## Scope

This phase creates database structure only. It does not seed users or students,
implement authentication, or connect frontend workflows to the database.

## Table Groups

- Auth and RBAC: `users`, `roles`, `user_roles`, `sessions`
- Institutes and student profile: `institutes`, `student_profiles`
- Academic records: `courses`, `enrollments`, `academic_summaries`
- Schedules and deadlines: `schedules`, `deadlines`
- Notifications and events: `notifications`, `notification_reads`, `events`
- Chat history: `conversations`, `messages`
- Support tickets: `tickets`, `ticket_messages`, `ticket_status_history`
- Smart suggestions: `student_question_events`, `question_trends`, `suggested_questions`
- Admin audit trail: `audit_logs`

## Constraints and Indexes

The migration uses `CHECK` constraints for controlled text fields such as user
status, student status, schedule type, notification status/type/priority, ticket
status/priority, message role, and suggestion source type. This keeps the schema
explicit while leaving room to evolve values in later migrations.

Indexes cover common lookup and list paths, including user email, session token
hashes, student IDs, student schedules/deadlines, notification windows, chat
messages, tickets, question trends, suggested questions, and audit logs.

## Updated Timestamps

The migration creates a generic `set_updated_at()` trigger function and attaches
it to app tables that have `updated_at`:

- `users`
- `student_profiles`
- `notifications`
- `conversations`
- `tickets`
- `suggested_questions`

## Reset

Development reset remains guarded by `APP_ENV` and `--yes`:

```bash
python scripts/db_reset.py --yes
```

The reset script drops only app-managed Postgres objects. It does not touch
Qdrant, Redis, `.env`, or database URLs.

## Secret Safety

Migration scripts use `APP_DATABASE_URL_DIRECT` internally and never print the
connection string. FastAPI runtime continues to use the pooled URL.
