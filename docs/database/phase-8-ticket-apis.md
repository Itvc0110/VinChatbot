# Phase 8: Ticket APIs

Phase 8 adds authenticated backend ticket APIs for student support workflows.
The APIs use the app Postgres database through the existing FastAPI database
pool and the session-based auth dependencies from Phase 6.

Frontend integration is planned for a later phase.

## Authorization

Use the opaque bearer token returned by `/auth/login`:

```http
Authorization: Bearer <token>
```

Student endpoints require the `student` role. Admin endpoints require one of:

- `global_admin`
- `institute_admin`
- `staff`

Student ticket access is scoped to the current student's own profile. Admin
ticket access is scoped as follows:

- `global_admin` can view all tickets.
- `institute_admin` and `staff` can view tickets for their institute when the
  current user context can be matched to an institute.

Cross-student or cross-institute access returns `404` where appropriate so the
API does not leak ticket existence.

## Student Endpoints

- `GET /tickets/me`
  - Lists tickets for the current student only.
- `GET /tickets/{ticket_id}`
  - Returns ticket detail for the current student only.
- `POST /tickets`
  - Creates a student-confirmed ticket.
  - New tickets use `status = submitted`, `confirmed_by_user = true`,
    `created_by_ai = false`, and `submitted_at = now()`.
  - Optional fields: `category`, `department`, `priority`,
    `include_chat_context`, `source_conversation_id`, and `origin_question`.
- `POST /tickets/{ticket_id}/messages`
  - Adds a student message to the current student's own ticket.

Example:

```bash
curl http://localhost:8000/tickets \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "subject": "Need enrollment help",
    "body": "I cannot enroll in CSC202.",
    "department": "Registrar",
    "category": "enrollment",
    "priority": "medium"
  }'
```

## Admin Endpoints

- `GET /admin/tickets`
  - Lists tickets visible to the current admin.
  - Optional query filters: `status`, `priority`, `include_archived`.
- `GET /admin/tickets/{ticket_id}`
  - Returns visible ticket detail.
- `PATCH /admin/tickets/{ticket_id}`
  - Updates `status`, `priority`, `assigned_admin_id`, `resolution`, or
    `archived`.
  - When `status` changes, a row is inserted into `ticket_status_history`.
- `POST /admin/tickets/{ticket_id}/messages`
  - Adds an admin message to a visible ticket.

Example:

```bash
curl http://localhost:8000/admin/tickets?status=submitted \
  -H "Authorization: Bearer <token>"
```

## Ticket Lifecycle

Allowed ticket statuses:

- `submitted`
- `open`
- `in_progress`
- `waiting_on_student`
- `resolved`
- `closed`

Allowed priorities:

- `low`
- `medium`
- `high`
- `urgent`

Responses do not include password hashes, session token hashes, or other
sensitive authentication material.
