# Known issue: two inconsistent student-enrollment data models

**Status:** open / demo-data issue (not a code bug). Surfaced while validating the Phase 5 personalization
tools. Affects what the chatbot reports for "my courses" vs "my schedule/transcript", and blocks a true
"next semester" feature. Documented here so anyone pulling the repo understands the discrepancy.

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
| Tools that read it | `get_my_schedule`, `get_my_transcript`, `get_my_curriculum_progress`, `get_my_course_eligibility`, `get_my_academic_standing` (GPA from `academic_summaries`) | `get_my_courses`, `get_my_deadlines`, `get_my_schedule` (fallback only) |

`student_profiles.id` is the shared key, but the two enrollment sets are seeded with **different courses and
even different course codes** for the same student.

## Concrete example — `student.cs.demo@vinuni.edu.vn`

- **Academic model** (`student_course_enrollments`, by term):
  - Fall 2025: GEN101 (completed) · Spring 2026: CS101 (completed), CS102 (failed) · **Summer 2026 (current):
    PE101 (completed), MATH102 / CS201 / GEN102 (enrolled), CS102 (retaking)**
- **Portal model** (`enrollments`): **CSC101, CSC250, CSC310, CSC330, ECE210 — all labeled "Fall 2026" /
  AY 2026-2027.**

So the chatbot will tell the same student:
- "What courses am I enrolled in?" → **`get_my_courses` (portal)** → CSC101/250/310/330, ECE210 (Fall 2026)
- "What's my schedule / what did I fail?" → **`get_my_schedule` / `get_my_transcript` (academic)** → CS102,
  MATH102, CS201, GEN102 (Summer 2026)

…i.e. **two different course lists**, with mismatched codes (CSC101 vs CS101). Both answers are individually
"correct" for the model they read; they just describe different worlds.

## Consequences

1. **"My courses" ≠ "my schedule/transcript"** — confusing for a student; the tools are faithful to their
   respective tables.
2. **No real "next semester" capability.** There is **no Fall 2026 `academic_term`**, **no `planned`
   future-term `student_course_enrollments`**, and **no `class_meetings` for a future term**. The only
   "future" data is the portal `enrollments` labeled Fall 2026, which `get_my_courses` returns but cannot be
   term-filtered or shown as a timetable. So "what classes do I have next semester?" can only echo the portal
   list — no next-semester schedule.
3. `get_my_courses` reads the portal model only, so it **omits the academic-model current-term enrollments**
   (the Summer 2026 courses the student is actually attending per the schedule).

## Recommendation (to unblock next-semester + remove the discrepancy)

1. **Pick one source of truth** for enrollments — preferably the academic model (`student_course_enrollments`
   + `academic_terms` + `class_meetings`), which is richer (terms, status, grades, timetable).
2. **Reconcile the demo seed**: align course codes (CSC* vs CS*) and make `enrollments` and
   `student_course_enrollments` describe the same courses, OR retire one table.
3. **Seed a Fall 2026 term** (`academic_terms`) + **`planned` `student_course_enrollments`** (+ optional
   `class_meetings`) for it. Then a term-aware `get_my_enrollments(term="current"|"next"|"all")` tool can
   answer "next semester's classes" cleanly. (Tool not built yet — pending this data.)
4. Until then, treat `get_my_courses` (portal/Fall-2026) and the academic-model schedule/transcript as
   **separate views**; don't assume they match.

Seed scripts live under `scripts/` (e.g. `seed_demo_data.py`); migrations under `migrations/`.
