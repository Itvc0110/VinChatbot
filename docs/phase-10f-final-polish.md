# Phase 10F Final Real-Data Polish

Phase 10F stabilizes the real-data frontend after Phases 10A through 10E. FastAPI remains the
only database access layer; the frontend continues to talk to backend routes through Next.js
`/api/*` rewrites.

## Polished

- Student and admin pages that read authenticated data now refetch when the access token changes.
- Local working copies for tickets and notifications reset on account changes, so switching users
  does not keep stale selections, optimistic edits, or read/archive overlays.
- Chat personal context now reloads on token changes, preventing one student's profile, schedule,
  deadlines, or tuition context from being reused for another student.
- Student schedule resets its auto-selected calendar month when the signed-in student changes.
- Admin knowledge-source reads now use the live `/sources` response directly. Backend errors show
  the normal retry state instead of silently falling back to mock rows.
- URL source indexing and re-crawl now surface real `/ingest/run` failures instead of simulating a
  successful result.
- Code comments now identify intentional local-only behavior and future backend contracts.

## Remaining Local Or Mock Behavior

These remain intentional because backend support does not exist yet:

- Student tuition data: future `GET /students/me/tuition`.
- Student notification read/important/archive/delete actions: Phase 11 notification mutations.
- Admin notification listing, draft/publish, and suggested-question generation: Phase 11.
- Student ticket archive/delete visibility: Phase 11 student ticket mutations.
- Admin unanswered queue and analytics: future admin review/analytics APIs.
- Binary source upload and source disable actions: future admin source-management APIs.
- Admin settings, context, events, logs, and a few demo-only UI toasts remain presentation demos.

## Phase 11

Move notification workflows to real backend APIs:

- admin notification list/create/update/publish
- student read/unread/important/archive mutations
- persisted notification-driven suggested-question generation/approval

Ticket archive/delete mutations and richer admin analytics can follow once those backend contracts
are defined.

## Verification

```bash
.venv/bin/python -m ruff check .
.venv/bin/python -m pytest
(cd frontend && npm run typecheck)
```

Results:

- Ruff: passed
- Pytest: `474 passed, 1 skipped`
- Frontend typecheck: passed
