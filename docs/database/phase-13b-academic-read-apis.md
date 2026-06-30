# Phase 13B: Academic Read APIs + Student Identity Binding

## Goal

Expose stable, read-only HTTP APIs so the dashboard, schedule page, and team tools can read the
**currently authenticated student's** academic data from the Phase 13A academic demo database.

Every student-facing endpoint resolves data through the authenticated user — never an arbitrary
`student_id` from the client:

```
current_user.id -> student_profiles.user_id -> student_profiles.id -> academic data
```

## What changed

Backend-only phase. No new migration (Phase 13A schema is reused as-is). FastAPI remains the only
structured-data access layer.

- `vinchatbot/app/repositories/academic.py` — added read-only query methods (below).
- `vinchatbot/app/services/academic.py` — **new** pure read-model/calculation service.
- `vinchatbot/app/schemas/academic.py` — added Phase 13B response models.
- `vinchatbot/app/api/routes_academic.py` — **new** router for `/academic/me*` and `/schedule/me`.
- `vinchatbot/app/main.py` — registered the academic router.
- Tests: `tests/test_academic_api.py` (route/identity/edge cases) and
  `tests/test_academic_service.py` (calculations); existing
  `tests/test_academic_repository.py` pure-helper tests are unchanged.

## APIs added

All endpoints require the `student` role: anonymous → **401**, non-student (admin/staff) → **403**,
authenticated student with no profile → **404**.

| Method & path | Returns |
| --- | --- |
| `GET /academic/me` | Overview: profile, faculty, program, current term, current GPA, cumulative CPA, earned/required credits, failed courses, currently enrolled courses, upcoming class meetings, progress summary. |
| `GET /academic/me/transcript` | All enrollments grouped by term with per-term GPA and running cumulative CPA, plus a transcript summary (attempted/earned/GPA credits, CPA, counted enrollment ids). |
| `GET /academic/me/curriculum` | Program curriculum bucketed into completed / in-progress / failed / remaining-required / remaining-0-credit, plus a progress summary. |
| `GET /academic/me/courses/eligible` | Next-course eligibility: eligible vs blocked courses with prerequisite/corequisite explanations, blocking reasons, already-completed / currently-enrolled flags, and retake/improvement possibility. |
| `GET /schedule/me?month=YYYY-MM` | Timetable events for the calendar month (VinUni local time): meeting id, course code/name, section code, instructor, meeting type, title, start/end, room name, building, note. |

`month` is validated as `YYYY-MM` (→ **422** on malformed input or month outside 01–12).

## Repository functions added (`AcademicRepository`)

All read-only:

- `get_student_profile_by_user(user_id)` — identity binding; joins `student_profiles` → `users`,
  `faculties`, `programs`. Returns `None` (→ 404) when the user has no student profile.
- `get_current_term(on_date=None)` — the term whose date range contains today (VinUni time), with a
  fallback to the most recently started term.
- `get_student_meetings_in_range(student_id, start_at, end_at)` — timetable events for the student's
  enrolled sections within a datetime window (used by both the monthly schedule and the overview's
  upcoming-meetings preview); spans terms so a month straddling two terms still returns every event.
- `get_requisite_status_bulk(student_id, course_ids, term_id)` — prerequisite/corequisite
  satisfaction for many courses in one query, grouped by `course_id` (bulk form of the existing
  `get_requisite_status`).
- `_fetchone` helper (mirrors the existing `_fetchall`).

Existing methods reused unchanged: `get_student_transcript`, `get_curriculum`,
`get_requisite_status`, and the pure helpers `is_failing_grade`, `enrollment_counts_for_gpa`,
`requisite_is_satisfied`.

## Service functions added (`services/academic.py`)

Pure functions that turn repository rows into response models (unit-tested without a DB):

- `compute_term_gpa`, `compute_cpa` — credit-weighted grade points.
- `compute_earned_credits`, `compute_failed_course_ids`, `_is_failed_attempt`.
- `build_transcript`, `build_transcript_summary` — term grouping + running CPA.
- `build_curriculum_progress` — status bucketing + progress summary.
- `build_course_eligibility` — eligible/blocked assembly with human-readable reasons.
- `build_overview` — the dashboard overview.
- `month_window(year, month)` — VinUni-local `[start, end)` month bounds for the schedule.

## Academic calculations implemented

- **GPA is per term; CPA is cumulative.** Both use weighted grade points:
  `SUM(grade_4 * credits) / SUM(credits)`, rounded to 2 places (half-up).
- **0-credit courses are excluded** from GPA/CPA (`enrollment_counts_for_gpa` requires `credits > 0`).
- **Failed courses grant no earned credits.** `earned_credits` sums course credits over distinct
  **passed** courses only.
- **Retake/improvement:** only the row with `is_gpa_counted = true` affects CPA. The Phase 13A
  partial unique index guarantees at most one counted attempt per course, so summing counted rows
  never double-counts.
- **Failed-course classification:** a course with a failing attempt that the student has neither
  since passed nor is currently retaking. A failed course currently being retaken is reported as
  *in-progress / enrolled*, not failed, so the overview and curriculum surfaces agree.
- **Prerequisite** = required course passed (≥ `min_grade_4`) in a term ending before the target
  term. **Corequisite** = passed earlier or taken in the same term. Blocking reasons are returned as
  clear English strings, e.g. *"Requires prerequisite CS102 (Data Structures) … passed before this
  term."*
- **Current GPA** is the current term's GPA, falling back to the most recent term with a computable
  GPA when the current term is still in progress.

## Identity binding behavior

- `/academic/me*` and `/schedule/me` take the authenticated user from the session and resolve the
  profile via `get_student_profile_by_user(current_user.id)`. The client cannot pass a `student_id`.
- A missing profile returns a 404 (`"Student academic profile not found."`).
- These endpoints never expose other students' records. Admin/global academic endpoints are out of
  scope for this phase (admins get 403 from the student-role guard).

## Verification commands

```bash
.venv/bin/python -m ruff check .
.venv/bin/python -m pytest
.venv/bin/python scripts/db_status.py
```

Docker smoke (logged in as `student.cs.demo@vinuni.edu.vn`, `2026-06-28`, term `2026-SUMMER`):

```bash
curl -s -X POST localhost:8000/auth/login -H 'Content-Type: application/json' \
  -d '{"email":"student.cs.demo@vinuni.edu.vn","password":"Demo@123456"}'   # access_token
curl -s localhost:8000/academic/me -H "Authorization: Bearer $TOKEN"
curl -s localhost:8000/academic/me/transcript -H "Authorization: Bearer $TOKEN"
curl -s localhost:8000/academic/me/curriculum -H "Authorization: Bearer $TOKEN"
curl -s localhost:8000/academic/me/courses/eligible -H "Authorization: Bearer $TOKEN"
curl -s "localhost:8000/schedule/me?month=2026-06" -H "Authorization: Bearer $TOKEN"
curl -s "localhost:8000/schedule/me?month=2026-07" -H "Authorization: Bearer $TOKEN"
```

Observed against live Neon data: overview returns CPA 3.12, earned 5 / required 120; transcript
groups FALL/SPRING/SUMMER with per-term GPA + running CPA; eligibility blocks CS201/CS301/CAP401 on
unmet prerequisites and lists the satisfied ones as eligible; schedule returns 6 June and 2 July
events; anonymous → 401, admin → 403.

## Notes / Known limitations

- Demo data only — not an official VinUni curriculum or transcript.
- `required_credits` comes from `programs.total_required_credits` (program-level), independent of the
  sum of curriculum-course credits.
- Eligibility considers the program **curriculum** courses; arbitrary catalog courses outside the
  student's curriculum are not enumerated. Completed courses below a 4.0 are surfaced as
  improvement-eligible; passed 4.0 courses and currently-enrolled courses are excluded from the
  eligible/blocked lists.
- Month windows are anchored to VinUni local time (`Asia/Ho_Chi_Minh`), matching how `timestamptz`
  meetings (+07) are stored.
- Read-only phase: no writes, no Vinnie personalization wiring, and no frontend changes. Auth,
  notifications, tickets, forum, and chat behavior are untouched.
