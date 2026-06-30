# Canonical Academic Single Source

## Decision

Frontend must call stable backend APIs only. It must not depend on database table names or legacy
portal storage. The canonical academic database model is:

- `student_course_enrollments`: course registration, transcript, GPA/CPA inputs, and earned credits.
- `student_schedule_events`: each student's calendar-ready class schedule.
- `class_meetings`: section-level timetable template used for planning/auditing, not the student UI source.
- `deadlines`: assignment/LMS/policy deadlines.
- `notifications` + `events`: announcements and campus event surfaces.

The legacy duplicate academic stores are removed by
`migrations/000010_canonical_academic_single_source.sql`:

- `enrollments`
- `schedules`
- `academic_summaries`

They are not recreated as tables or views. Existing frontend screens keep calling stable API
endpoints such as `/api/students/me/schedule`, `/api/academic/me`, and `/api/schedule/me`; the
backend now maps those responses from the canonical tables.

## Calendar Rules

`student_schedule_events` stores both:

- `start_at` / `end_at`: timezone-aware timestamps for querying, sorting, and API responses.
- `start_time` / `end_time`: local VinUni time-of-day fields for fast calendar rendering.

Database constraints enforce:

- `end_at > start_at`
- `start_time < end_time`
- one student cannot have overlapping class/lab/tutorial/seminar/exam/office-hour events

Adjacent classes are allowed when the next `start_at` equals the previous `end_at`.

## Changed Files

- `migrations/000010_canonical_academic_single_source.sql`
  - Drops `enrollments`, `schedules`, and `academic_summaries`.
  - Adds local `start_time` / `end_time` columns to `class_meetings`.
  - Creates `student_schedule_events`.
  - Adds a per-student no-overlap exclusion constraint.
- `docs/database/realistic-student-seed-100.sql`
  - Seeds canonical academic data only.
  - Inserts calendar rows into `student_schedule_events`, not `schedules`.
- `vinchatbot/app/repositories/students.py`
  - Keeps stable `/students/me/*` API shapes, but reads canonical tables.
- `vinchatbot/app/repositories/academic.py`
  - Reads student schedule APIs from `student_schedule_events`.
- `vinchatbot/app/repositories/admin_dashboard.py`
  - Counts and lists upcoming schedules from `student_schedule_events`.
- `scripts/db_reset.py`
  - Drops both old legacy relations and new canonical relations safely during reset.

## Reset / Recreate / Seed

Use only in a safe environment. `scripts/db_reset.py` refuses `APP_ENV=production`.

```bash
.venv/bin/python scripts/db_reset.py --yes
.venv/bin/python scripts/db_migrate.py
psql "$APP_DATABASE_URL_DIRECT" -v ON_ERROR_STOP=1 -f docs/database/realistic-student-seed-100.sql
```

If `psql` is not installed locally, run the same seed SQL from your database console, or install the
PostgreSQL client and use the command above.

## Sanity Checks

Legacy relations should not exist:

```sql
select relname, relkind
from pg_class c
join pg_namespace n on n.oid = c.relnamespace
where n.nspname = 'public'
  and relname in ('enrollments', 'schedules', 'academic_summaries');
```

Expected: zero rows.

Seeded data counts:

```sql
with seeded as (
    select id from student_profiles
    where student_code ~ '^VU(22|23|24|25)(VIB|CECS|CHS|CASE)[0-9]{3}$'
)
select count(*) from seeded;

with seeded as (
    select id from student_profiles
    where student_code ~ '^VU(22|23|24|25)(VIB|CECS|CHS|CASE)[0-9]{3}$'
)
select count(*) from student_course_enrollments
where status = 'enrolled'
  and student_id in (select id from seeded);

with seeded as (
    select id from student_profiles
    where student_code ~ '^VU(22|23|24|25)(VIB|CECS|CHS|CASE)[0-9]{3}$'
)
select count(*) from student_schedule_events
where student_id in (select id from seeded);
```

With the realistic 100-student seed, expected counts are:

- Seeded students: `100`
- Canonical current enrollments: `596`
- Canonical completed transcript rows: `1282`
- Student calendar events: `9855` for June/July 2026
- Deadlines: `200`

No-overlap check:

```sql
select count(*) as overlapping_pairs
from student_schedule_events a
join student_schedule_events b
  on b.student_id = a.student_id
 and b.id > a.id
 and tstzrange(a.start_at, a.end_at, '[)') && tstzrange(b.start_at, b.end_at, '[)');
```

Expected: `0`.

## UI Smoke Test

Start backend and frontend, then login with any seeded student account from
`docs/database/realistic-student-seed-100.sql`.

```bash
.venv/bin/uvicorn vinchatbot.app.main:app --reload --port 8000
```

In another terminal:

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000/login`.

Smoke-test these pages:

- `/student/dashboard`
- `/student/academic`
- `/student/schedule`
- `/student/notifications`
- `/student/support`
- `/student/forum`
