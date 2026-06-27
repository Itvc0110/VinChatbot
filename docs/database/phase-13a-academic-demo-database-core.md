# Phase 13A: Academic Demo Database Core

## Goal

Create a database-first mock academic core so backend APIs/tools can query realistic academic data before frontend integration is complete.

This data is development/demo data only. It is not an official VinUni curriculum.

## What Changed

- Added an additive SQL migration: `migrations/000007_academic_demo_database_core.sql`.
- Added academic catalog, curriculum, requisite, transcript, section, room, and class meeting tables.
- Extended existing `student_profiles` and `courses` in place so current student APIs keep their existing columns while academic-core callers can use the new normalized fields.
- Added a small read-oriented academic repository and Pydantic schemas.
- Updated development reset coverage for the new tables and enrollment normalization function.

## Tables Added/Changed

Added:

- `faculties`
- `programs`
- `academic_terms`
- `curriculum_courses`
- `course_requisites`
- `rooms`
- `course_sections`
- `student_course_enrollments`
- `class_meetings`

Extended:

- `student_profiles`: `student_code`, `full_name`, `faculty_id`, `program_id`, `cohort_year`, `current_year`, `status`
- `courses`: `code`, `name`, `course_level`, `department_code`, `is_general_education`, `description`; credits now allow the demo-supported set `0, 2, 3, 4`

## Seed Data Added

- Faculties/programs for Computer Science, Business Administration, Health Sciences, and General Education Foundation.
- Academic terms including Summer Term 2026:
  - `2026-SUMMER`
  - `2026-06-01` to `2026-07-31`
- Five linked demo student profiles across the academic programs.
- Fifteen mock catalog courses, including the requested GEN, MATH, CS, BUS, ECON, BIO, HS, PE, and CAP courses.
- Curriculum rows for every seeded program.
- Course requisites:
  - `CS102` prerequisite `CS101`
  - `CS201` prerequisite `CS102`
  - `CS201` corequisite `MATH102`
  - `CS301` prerequisite `CS102`
  - `CAP401` prerequisite `CS201`
- Transcript examples for passed courses, failed courses, retakes, improvements, current enrollments, and zero-credit PE.
- Summer 2026 course sections, rooms, and class meetings covering lectures, labs, seminars, office hours, quizzes, midterms, final exams, and assignment deadlines.

## Academic Rules Implemented

- Course credits support `0`, `2`, `3`, and `4`.
- Zero-credit courses are valid and are forced out of GPA counting by the enrollment normalization trigger.
- Failing grades normalize to `letter_grade = 'F'`, `passed = false`, and `earned_credits = 0`.
- Retake and improvement examples are stored as new `student_course_enrollments` rows; old transcript rows are preserved.
- A partial unique index allows only one selected GPA/CPA-counted attempt per student/course.
- Prerequisite/corequisite semantics are represented in `course_requisites` and in the lightweight repository helper.

## Verification Commands

```bash
python scripts/db_migrate.py
python scripts/db_status.py
pytest tests/test_db_migrations.py tests/test_academic_repository.py tests/test_seed_demo_data.py
```

## Notes / Known Limitations

- Phase 13A does not add frontend screens or public API routes.
- The migration seeds mock academic users with null password hashes to avoid storing plaintext or new demo credentials in SQL. Existing Phase 5A demo users keep their password hashes if they already exist.
- Existing `courses` and `student_profiles` remain backward compatible with earlier portal code; the new fields are additive.
- Requisite enforcement is modeled for callers and helpers, but course registration write workflows are not part of this phase.
