# Phase 10D: Ticket UI Backend Integration

Phase 10D connects the existing student and admin ticket interfaces to the
Phase 8 FastAPI ticket APIs. The UI keeps the established support-ticket layout
and uses the Phase 10A bearer-token helper for all requests.

## APIs Integrated

Student:

- `GET /tickets/me`
- `GET /tickets/{ticket_id}`
- `POST /tickets`
- `POST /tickets/{ticket_id}/messages`

Admin:

- `GET /admin/tickets`
- `GET /admin/tickets/{ticket_id}`
- `PATCH /admin/tickets/{ticket_id}`
- `POST /admin/tickets/{ticket_id}/messages`

The browser reaches these through Next rewrites:

- `/api/tickets/*`
- `/api/admin/tickets/*`

## Student Flow

The student support page loads the signed-in student's tickets from
`GET /tickets/me`. Opening a ticket fetches detail and thread messages from
`GET /tickets/{ticket_id}`. Student replies are posted with
`POST /tickets/{ticket_id}/messages`.

Manual ticket creation and Vinnie escalation both keep the review-before-send
flow: the student edits a draft, optionally includes chat context, and only then
submits to `POST /tickets`.

## Admin Flow

The admin ticket console loads scoped tickets from `GET /admin/tickets`.
Selecting a ticket fetches full detail from `GET /admin/tickets/{ticket_id}`.
Admins can reply with `POST /admin/tickets/{ticket_id}/messages` and update
status or priority with `PATCH /admin/tickets/{ticket_id}`.

Backend RBAC determines whether the current admin sees global or institute-only
tickets.

## Field Mapping

The frontend accepts both UI and backend naming for ticket creation:

- `title` maps to `subject`
- `description` maps to `body`

The backend stores native statuses such as `open`, `in_progress`, and
`waiting_on_student`. Older frontend aliases remain tolerated at the API layer
and are mapped before sending updates.

When a ticket is prepared from chat, `source_conversation_id` uses the backend
Postgres conversation UUID when available. Legacy `web-*` chat thread ids are
not sent to the ticket API because the backend field is a UUID foreign key.

## Loading And Errors

Existing `useAsync()` and page-level empty states remain in place for list
loading, retry, and empty results. Detail fetch, create, reply, and update
failures surface through the existing toast pattern.

## Known Limitations

- Student archive/delete actions remain local visibility controls because Phase
  8 does not expose student archive/delete endpoints.
- Draft saving remains local-only; only confirmed submissions are sent to the
  backend.
