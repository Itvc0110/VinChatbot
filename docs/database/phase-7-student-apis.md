# Phase 7: Student APIs

Phase 7 adds read-only backend Student APIs backed by the app Postgres database.
All endpoints require a valid session token from `/auth/login`.

## Authorization

Use the opaque bearer token returned by login:

```http
Authorization: Bearer <token>
```

Example:

```bash
curl http://localhost:8000/students/me \
  -H "Authorization: Bearer <token>"
```

Frontend integration is planned for a later phase.

## Endpoints

- `GET /students/me`
  - Returns the current student's profile, institute, and academic summary.
- `GET /students/me/courses`
  - Returns the current student's enrolled courses.
- `GET /students/me/schedule`
  - Returns schedule rows for the current student.
  - Query: `upcoming_only=true|false`, default `true`.
- `GET /students/me/deadlines`
  - Returns deadlines for the current student.
  - Query: `upcoming_only=true|false`, default `true`.
- `GET /students/me/notifications`
  - Returns published notifications targeted to the current student.
  - Includes `is_read`, `important`, and `archived` from `notification_reads`.
- `GET /suggestions/me`
  - Returns active suggested questions grouped for the current student.

## Notification Targeting

Notifications are returned when they are published, inside their valid
`start_date` / `end_date` window, and match at least one current-student context:

- `target_scope = all`
- `target_scope = institute` and the institute matches the student profile
- `target_scope = course` and the course is one of the student's enrollments
- `target_scope = cohort` and the cohort matches the student profile

The API does not implement mark-read or archive mutations yet.

## Suggestion Grouping

`GET /suggestions/me` returns:

```json
{
  "for_you": [],
  "trending_now": [],
  "from_announcements": [],
  "from_events": []
}
```

Grouping uses `source_type`, plus seeded category/trigger hints where needed:

- `trend` -> `trending_now`
- `notification` -> `from_announcements`
- `event` or event-like category/trigger -> `from_events`
- schedule, deadline, ticket, personal, and unknown values -> `for_you`

Responses never include password hashes, token hashes, or another student's
private data.
