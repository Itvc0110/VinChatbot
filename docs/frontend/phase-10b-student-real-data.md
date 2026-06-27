# Phase 10B: Student Portal Real Data

Phase 10B replaces the student portal's main read-only mock data with the real
FastAPI Student APIs from Phase 7. Requests use the Phase 10A bearer-token
helper, so the backend resolves data for the signed-in student.

## APIs Integrated

- `GET /students/me`
- `GET /students/me/courses`
- `GET /students/me/schedule`
- `GET /students/me/deadlines`
- `GET /students/me/notifications`
- `GET /suggestions/me`

The browser calls these through Next rewrites:

- `/api/students/*`
- `/api/suggestions/*`

## Frontend Entry Points

Updated API functions in `frontend/lib/api.ts`:

- `getStudentMe()`
- `getStudentCourses()`
- `getStudentProfile()`
- `getStudentSchedule()`
- `getStudentDeadlines()`
- `getStudentNotifications()`
- `getSuggestedQuestions()`
- `getActiveSuggestedQuestions()`
- `getStudentCalendar()`

Existing pages/components continue to consume the established UI-facing types:

- Student dashboard/profile cards
- Student calendar/schedule page
- Student notifications page
- Student notification bell
- Student chat suggestion chips/cards
- Chat personalization context

`getStudentCalendar()` now composes real schedule and deadline API responses.
Campus events remain empty until a dedicated backend student-events endpoint is
added.

The schedule page initializes its calendar cursor from real event dates: it opens
to the nearest upcoming class/deadline month, falls back to the most recent event
month when all events are in the past, and uses the current month only when no
events exist. Manual month/day navigation is preserved after the page loads.

## Loading, Error, And Empty States

The existing `useAsync()` and `AsyncBoundary` patterns remain in use:

- Loading states render skeleton rows or existing placeholders.
- Errors surface with retry where the page already supports it.
- Empty arrays render the existing empty states.

Notification read/important/archive/delete controls remain local-only because
Phase 7 does not include notification mutation endpoints.

## Demo Account Personalization

Because the API calls are scoped by bearer auth, each seeded demo student sees
their own Neon-backed institute, courses, schedule, deadlines, notifications,
and suggestions:

- `student.cs.demo@vinuni.edu.vn` -> CECS
- `student.business.demo@vinuni.edu.vn` -> VIB
- `student.health.demo@vinuni.edu.vn` -> CHS
- `student.liberal.demo@vinuni.edu.vn` -> CASE

## Known Limitations

- Ticket list/mutation UI is still mock-backed and will be integrated later.
- Tuition remains mock-backed until a backend tuition endpoint exists.
- Conversation/chat history UI is not integrated in this phase.
- Campus event listing has no dedicated student API yet; calendar/event pages
  show real classes and deadlines from schedule/deadline APIs.
