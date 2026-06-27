# Phase 11D: Notification UX Audit

Phase 11D polishes the notification workflow built in Phases 11A-11C without
adding new notification schema or model/RAG behavior.

## Student UX

- The student notification page now exposes only backend-persisted notification
  actions: read, unread, and mark all read.
- Opening a notification detail view marks unread items as read and persists the
  state through the student notification API.
- The bell listens for notification changes and refetches so unread counts stay
  aligned after page actions, route changes, account switches, and refreshes.
- Local-only archive/delete/important actions were removed from the student
  notification API client to avoid demo state drift.

## Detail View

The lightweight detail modal shows the notification title, message, type, read
state, priority, lifecycle status, start/end dates, deadline/event dates, and
related links or Vinnie question deep links when present.

## Admin UX

- Admin notification create/edit validates blank title, blank message, missing
  institute target, missing schedule time, and invalid active windows before
  submitting.
- Publish and archive actions ask for confirmation to prevent accidental
  lifecycle changes.
- Status and target badges are shown with readable labels.
- Successful create/edit/publish/schedule/archive actions update the local list.

## Backend Guardrails

The admin notification request models now reject whitespace-only title/message
fields with controlled validation errors. Existing lifecycle semantics remain:
draft and archived notifications stay hidden from students, future scheduled
notifications stay hidden, and targeting rules remain unchanged.

## Known Limitations

- Student important/archive/delete preference mutations are intentionally not
  implemented yet; those controls are hidden until backend endpoints exist.
- Admin notification creation is still deterministic and form-based; full admin
  notification campaign tooling is out of scope.
- Vinnie suggestions remain deterministic/rule-based and do not call an LLM.

## Verification

- `.venv/bin/python -m ruff check .` passed.
- `.venv/bin/python -m pytest` passed: 506 passed, 1 skipped.
- `(cd frontend && npm run typecheck)` passed.
- Docker compose rebuild passed.
- Docker smoke passed for admin draft/edit/publish/archive, matching student
  visibility, read/unread/mark-all-read persistence, notification-driven
  suggestions, and non-matching student isolation.
