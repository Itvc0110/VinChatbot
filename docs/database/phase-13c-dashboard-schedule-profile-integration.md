# Phase 13C: Dashboard / Schedule / Profile Academic Integration

## Goal

Wire the student-facing frontend (dashboard, calendar/schedule, and a new academic record page) to
the Phase 13B academic read APIs, which resolve data through the authenticated session
(`current_user.id -> student_profiles.user_id -> student_profiles.id`). The frontend never sends a
`student_id`. Frontend-integration only — no backend logic, no new migration, no Vinnie
personalization.

## What changed

- **API client** (`frontend/lib/api.ts`): added typed models and fetch functions for all five
  academic endpoints, following the existing `getJSON`/`ApiError` conventions.
- **Proxy** (`frontend/next.config.js`): added `/api/academic/*` → `/academic/*` and
  `/api/schedule/*` → `/schedule/*` rewrites (browser → Next → FastAPI, same pattern as
  `/api/students/*`).
- **Dashboard** (`app/student/dashboard/page.tsx`): reads `GET /academic/me`; GPA/credits now come
  from the academic record, and a new **Academic Progress** card shows CPA, a credit progress bar,
  required-course counts, currently-enrolled and failed-course chips, and upcoming class meetings.
- **Schedule** (`app/student/schedule/page.tsx`): class events for the visible month now come from
  `GET /schedule/me?month=YYYY-MM` instead of the legacy recurring schedule; deadlines/events still
  come from the existing calendar source.
- **Academic record page** (`app/student/academic/page.tsx`, **new**): transcript, curriculum
  progress, and course eligibility. Linked from a new **Academic** top-nav item
  (`components/shell/StudentTopNav.tsx`) and from the dashboard's Academic Progress card.

## Pages / components updated

| File | Change |
| --- | --- |
| `frontend/lib/api.ts` | Academic types + `getAcademicOverview`, `getAcademicTranscript`, `getAcademicCurriculum`, `getEligibleCourses`, `getMonthlySchedule`. |
| `frontend/next.config.js` | `/api/academic/*` and `/api/schedule/*` rewrites. |
| `frontend/app/student/dashboard/page.tsx` | Academic Profile card sourced from `/academic/me`; new Academic Progress card. |
| `frontend/app/student/schedule/page.tsx` | Month-scoped `/schedule/me` class meetings merged into the calendar; empty/error notes. |
| `frontend/app/student/academic/page.tsx` | **New** transcript / curriculum / eligibility page. |
| `frontend/components/shell/StudentTopNav.tsx` | New **Academic** nav item (EN "Academic" / VI "Học tập"). |

## API client functions / types added

Functions: `getAcademicOverview()`, `getAcademicTranscript()`, `getAcademicCurriculum()`,
`getEligibleCourses()`, `getMonthlySchedule(month)`.

`getMonthlySchedule` validates `YYYY-MM` client-side (`ACADEMIC_MONTH_RE`) and throws
`ApiError(…, 422)` before calling, so an invalid month never reaches the API.

Types (JSON mirrors of the FastAPI models; `Decimal` fields arrive as strings):
`AcademicOverview`, `AcademicScheduleEvent`, `AcademicTranscript` (+ `AcademicTranscriptTerm`,
`AcademicTranscriptSummary`, `AcademicEnrollment`), `AcademicCurriculumProgress`
(+ `CurriculumProgressCourse`), `AcademicEligibility` (+ `EligibleCourse`,
`AcademicRequisiteExplanation`), and the shared `AcademicProfile`, `AcademicProgram`,
`AcademicFaculty`, `AcademicTerm`, `AcademicCourse`, `AcademicProgressSummary`, plus the
literal unions (`AcademicMeetingType`, `AcademicEnrollmentStatus`, `CurriculumProgressStatus`,
`AcademicCurriculumCategory`, `AcademicRequisiteType`).

## Error / loading / empty states

- **Dashboard** Academic Progress card: skeleton-ish "…" while loading; a neutral
  *"Academic data is unavailable right now."* on error (the rest of the dashboard keeps working);
  per-section empty text ("None", "No upcoming classes.").
- **Schedule**: the existing `AsyncBoundary` covers the calendar load; a `cal-empty` note shows
  *"No classes scheduled this month."* when the month has no meetings, and
  *"Couldn't load your class schedule for this month."* if `/schedule/me` errors. The calendar still
  renders deadlines/events meanwhile.
- **Academic record page**: each section (transcript/curriculum/eligibility) has its own
  loading / empty / error handling with a status-aware message and a Retry button:
  - **401** → "Please sign in to view your academic record."
  - **403** → "This page is available to students only."
  - **404** → "No academic profile is linked to your account yet."
  - otherwise → the backend detail or a generic message.
  (The route is also wrapped by `ProtectedRoute role="student"`, which redirects anonymous → `/login`
  and non-students → `/403` before the page renders; the per-status messages cover a mid-session
  token expiry / missing profile.)
- **422 month**: guarded client-side in `getMonthlySchedule`; the page only ever derives `month`
  from the calendar cursor, so a valid value is always sent.

## Verification commands

```bash
cd frontend
npm run typecheck   # tsc --noEmit — passes
npm run build       # next build — passes (27 routes, incl. /student/academic)
# npm run lint is the interactive `next lint` setup prompt in this repo (ESLint not configured) — skipped
```

Docker smoke (frontend proxy → FastAPI, logged in as `student.cs.demo@vinuni.edu.vn`):

```bash
curl -s localhost:3000/api/academic/me -H "Authorization: Bearer $TOKEN"          # CPA 3.12, enrolled CS102/MATH102, 2 upcoming meetings
curl -s "localhost:3000/api/schedule/me?month=2026-06" -H "Authorization: Bearer $TOKEN"  # 6 June events
curl -s "localhost:3000/api/schedule/me?month=2026-13" -H "Authorization: Bearer $TOKEN" -o /dev/null -w "%{http_code}"  # 422
curl -s localhost:3000/student/academic -o /dev/null -w "%{http_code}"            # 200
```

## Addendum — denser June/July schedule seed (migration 000008)

To make the calendar look like a real timetable, `migrations/000008_academic_demo_schedule_density.sql`
(mock demo data) adds:

- A few more **2026-SUMMER enrollments** for the primary demo students (status `enrolled`, plus a
  `retaking` for the liberal-studies student's failed GEN101) so each has ~4–5 summer courses. New
  enrollments carry no grades, so transcript GPA/CPA are unchanged; they show as *in-progress* in
  curriculum and as *currently enrolled* (excluded) in eligibility.
- A **recurring weekly timetable** for every 2026-SUMMER section across `2026-06-01 .. 2026-07-31`,
  generated with `generate_series` from a per-section weekday/time slot template (Mon–Fri, plus a
  Saturday PE session). Meeting instants are built in `Asia/Ho_Chi_Minh` to match the stored
  `timestamptz` data. Titles encode course + session type + weekday, so re-running is idempotent
  (`on conflict (section_id, title, start_at) do update`); the one-off lecture/exam/deadline rows
  from migration 000007 are preserved.

Result (verified via `GET /schedule/me`): the CS demo student now has ~80 June / ~74 July sessions,
**2–4 classes on most weekdays** (Mon–Sat); other demo students land in a similar 1–5/day range
depending on their program's summer load. Apply with `.venv/bin/python scripts/db_migrate.py`
(restart the backend afterward if its Neon pool has gone idle).

## Notes / Known limitations

- The schedule calendar now renders dated class meetings from `/schedule/me` for the **visible
  month** (re-fetched on month navigation). Legacy recurring class events are dropped; deadlines and
  general events still come from `getStudentCalendar`. Class events outside the cursor month are not
  loaded until you navigate to that month.
- `month` is derived from the cursor in browser-local wall-clock; the backend window is VinUni-local
  (`Asia/Ho_Chi_Minh`). For typical daytime classes this matches; meetings within a few hours of a
  month boundary in a very different timezone could shift months.
- The dashboard's right-rail "Today's Schedule" still uses the legacy recurring schedule
  (`getStudentSchedule`); it was left unchanged to keep this phase focused. Upcoming dated meetings
  are surfaced in the new Academic Progress card instead.
- GPA/CPA/percent values render as backend-provided strings (no client recomputation).
- No new database migration; notifications, tickets, forum, chat, and admin behavior are untouched.
- Vinnie academic personalization is intentionally not implemented in this phase.
