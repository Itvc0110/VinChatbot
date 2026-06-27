# Phase 11B: Admin Notifications

Phase 11B turns notifications into a real admin-to-student workflow backed by FastAPI and Neon/Postgres.

## Endpoints

- `GET /admin/notifications`
- `GET /admin/notifications/targets`
- `GET /admin/notifications/{notification_id}`
- `POST /admin/notifications`
- `PATCH /admin/notifications/{notification_id}`
- `POST /admin/notifications/{notification_id}/publish`
- `POST /admin/notifications/{notification_id}/schedule`
- `POST /admin/notifications/{notification_id}/archive`

Student read state remains handled by the Phase 11A endpoints under `/students/me/notifications`.

## RBAC

All admin notification endpoints require one of:

- `global_admin`
- `institute_admin`
- `staff`

Anonymous users receive `401`. Student users receive `403`.

`global_admin` can manage all notification targets. `institute_admin` and `staff` use the same conservative institute scoping pattern as admin tickets: they can manage only notifications targeted to their own institute.

## Lifecycle

Supported statuses:

- `draft`
- `scheduled`
- `published`
- `archived`

Draft and archived notifications are hidden from students. Published notifications are visible when their target matches the current student and the active date window allows it. Scheduled notifications use `start_date` as the publish time and become visible at read time when `start_date <= now()`. No background worker is required.

## Targeting

Phase 11B supports:

- all students
- institute-specific students

The existing student notification repository enforces visibility by status, active date window, and target scope. Phase 11A read/unread state still persists in `notification_reads`.

## Frontend

The admin page at `/admin/notifications` now uses the real backend API. Admins can list, create, edit, publish now, schedule, and archive notifications. The page continues to use the existing admin card/composer styling.

## Known Limitations

- No email or push delivery.
- No background scheduler; scheduled visibility is query-time based.
- Forum-linked notifications are not expanded in this phase.
- Suggested-question generation remains the existing frontend rule-based helper and is not part of the backend admin workflow.
