# Phase 11A: Student Notification Actions

Phase 11A persists student notification read state through FastAPI and Neon/Postgres. The frontend still reads notifications with `GET /students/me/notifications`, but read/unread actions are no longer local-only.

## Endpoints

- `POST /students/me/notifications/{notification_id}/read`
- `POST /students/me/notifications/{notification_id}/unread`
- `POST /students/me/notifications/mark-all-read`

All endpoints require an authenticated bearer token with the `student` role.

## RBAC And Visibility

Students can mutate only notifications visible to their own profile. Visibility uses the same rules as the notification list:

- published status
- active start/end date window
- `target_scope` of `all`, `institute`, `course`, `cohort`, or direct `student`
- the current student's institute, enrolled courses, cohort, or user id

Anonymous requests return `401`. Non-student roles return `403`. Missing or invisible notifications return `404`.

## Frontend Integration

The student notification page and notification bell now call the student notification action APIs. Read/unread and mark-all-read state persists after refresh and after account switching. Mutations use optimistic UI with rollback on failure.

## Known Limitations

Phase 11A does not add admin notification creation or publishing. Important, archive, delete, and admin notification management remain future backend work for Phase 11B or later.

Forum notification deep links are nullable in the student notification response. If the deployed database has not applied the forum migration yet, student notifications still load and forum endpoints return a controlled `503` explaining that forum migrations must be applied, rather than surfacing raw `UndefinedColumn` or `UndefinedTable` database errors.
