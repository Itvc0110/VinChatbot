# Known issue: two inconsistent student-enrollment data models

**Status:** partially mitigated in code; underlying demo-data issue remains. Surfaced while validating
the Phase 5 personalization tools. The chatbot now uses the Phase 13 academic read-model for profile,
GPA/CPA, current courses, current schedule context, curriculum, eligibility, and GPA projection, so it
matches `student/dashboard` and `student/academic`. The older portal enrollment/deadline tables still
exist and can still block a true "next semester" feature until the seed data is reconciled.

## The two models

The DB carries **two parallel, independently-seeded representations of a student's courses** that do **not
agree**:

| | Academic model (Phase 13A) | Portal model (Phase 10–12) |
|---|---|---|
| Enrollment table | `student_course_enrollments` (has `term_id`, `status`, grades) | `enrollments` |
| Course table cols | `courses.code` / `course_title` | `courses.course_code` / `course_title` |
| Term structure | `academic_terms` (Fall 2025 / Spring 2026 / Summer 2026) | none — `courses.semester` / `academic_year` strings only |
| Timetable | `class_meetings` (UTC, per section) | `schedules` |
| Deadlines | — | `deadlines` |
| Tools that read it | `get_my_profile`, `get_my_academic_standing`, `get_my_courses`, `get_my_schedule`, `get_my_transcript`, `get_my_curriculum_progress`, `get_my_course_eligibility`, `project_gpa_for_target`; chat personalization context for profile/current courses/schedule | `get_my_deadlines` and activity surfaces; `get_my_schedule` only as fallback when no academic timetable exists |

`student_profiles.id` is the shared key, but the two enrollment sets are seeded with **different courses and
even different course codes** for the same student.

## Concrete example — `student.cs.demo@vinuni.edu.vn`

- **Academic model** (`student_course_enrollments`, by term):
  - Fall 2025: GEN101 (completed) · Spring 2026: CS101 (completed), CS102 (failed) · **Summer 2026 (current):
    PE101 (completed), MATH102 / CS201 / GEN102 (enrolled), CS102 (retaking)**
- **Portal model** (`enrollments`): **CSC101, CSC250, CSC310, CSC330, ECE210 — all labeled "Fall 2026" /
  AY 2026-2027.**

Previously the chatbot could tell the same student two different course lists:
`get_my_courses` read portal rows (CSC101/250/310/330, ECE210), while schedule/transcript read academic rows
(CS102, MATH102, CS201, GEN102). This has been mitigated by making chat personal tools and backend
personalization context prefer the academic read-model for academic identity/current-course facts.

## Consequences

1. **Legacy portal course/deadline data still exists** — chat filters course-specific deadlines against
   current academic courses, but the seed data itself still describes a separate Fall 2026 world.
2. **No real "next semester" capability.** There is **no Fall 2026 `academic_term`**, **no `planned`
   future-term `student_course_enrollments`**, and **no `class_meetings` for a future term**. The only
   "future" data is the portal `enrollments` labeled Fall 2026, which `get_my_courses` returns but cannot be
   term-filtered or shown as a timetable. So "what classes do I have next semester?" can only echo the portal
   list — no next-semester schedule.
3. The portal/dashboard activity widgets that intentionally read `deadlines`, `notifications`, or
   suggestions may still surface legacy demo activity until those seeds are reconciled.

## Recommendation (to unblock next-semester + remove the discrepancy)

1. **Pick one source of truth** for enrollments — preferably the academic model (`student_course_enrollments`
   + `academic_terms` + `class_meetings`), which is richer (terms, status, grades, timetable).
2. **Reconcile the demo seed**: align course codes (CSC* vs CS*) and make `enrollments` and
   `student_course_enrollments` describe the same courses, OR retire one table.
3. **Seed a Fall 2026 term** (`academic_terms`) + **`planned` `student_course_enrollments`** (+ optional
   `class_meetings`) for it. Then a term-aware `get_my_enrollments(term="current"|"next"|"all")` tool can
   answer "next semester's classes" cleanly. (Tool not built yet — pending this data.)
4. Until then, treat the portal/Fall-2026 activity seed as demo-only support data; do not use it as the
   source of truth for academic identity, current courses, GPA/CPA, or transcript answers.

Seed scripts live under `scripts/` (e.g. `seed_demo_data.py`); migrations under `migrations/`.
