# Phase 10E Admin Dashboard

Phase 10E replaces the admin dashboard mock data with a read-only FastAPI endpoint:

```bash
GET /admin/dashboard
```

The frontend calls this through the existing Next.js proxy at `/api/admin/dashboard`. The
browser never connects directly to Neon/Postgres.

## RBAC

- Anonymous requests return `401`.
- Student users return `403`.
- `global_admin` users see aggregate dashboard data across all institutes.
- `institute_admin` and `staff` users use the same institute scoping pattern as the admin ticket APIs.

## Response

The response contains:

- overview counts for students, tickets, upcoming academic items, and published notifications
- ticket counts by status
- ticket counts by priority
- student counts by institute
- recent tickets
- upcoming deadlines, schedules, events, and notifications

Only safe aggregate and dashboard display fields are returned. Password hashes, session token
hashes, database URLs, and other secrets are not included.

## Frontend

`frontend/app/admin/dashboard/page.tsx` now uses `getAdminDashboard()` from
`frontend/lib/api.ts`. It shows loading, error/retry, and empty states while preserving the
existing admin dashboard layout and quick actions.

## Limitations

- The dashboard is read-only.
- Admin notification, analytics, and knowledge-source pages still have their own phase-specific
  integrations or mock fallbacks.
- Ticket mutations remain handled by the Phase 10D ticket console.
