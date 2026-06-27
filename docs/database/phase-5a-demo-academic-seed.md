# Phase 5A: Demo Academic Seed

Phase 5A adds deterministic development demo users and academic data through a
seed script instead of a migration:

```bash
python scripts/seed_demo_data.py --section academic --yes
```

The script uses `APP_DATABASE_URL_DIRECT`, refuses production environments, and
does not print database URLs or credentials.

## Seeded Data

- 50 demo student users
- 5 demo admin/staff users
- Student profiles for all demo students
- Academic GPA summaries
- Institute courses
- Student enrollments
- Student class/lab/exam/advising schedules
- Student academic deadlines

Student distribution:

- `VIB`: 20 students
- `CECS`: 15 students
- `CHS`: 10 students
- `CASE`: 5 students

## Demo Student Accounts

- `student.business.demo@vinuni.edu.vn`
- `student.cs.demo@vinuni.edu.vn`
- `student.health.demo@vinuni.edu.vn`
- `student.liberal.demo@vinuni.edu.vn`

## Demo Admin Accounts

- `admin.global.demo@vinuni.edu.vn`
- `admin.business.demo@vinuni.edu.vn`
- `admin.cecs.demo@vinuni.edu.vn`
- `admin.health.demo@vinuni.edu.vn`
- `admin.liberal.demo@vinuni.edu.vn`

## Demo Password

All seeded demo accounts use the development-only password:

```text
Demo@123456
```

Only password hashes are stored in Postgres. Do not use this password outside
local or development demo environments.

## Idempotency

The seed script uses stable identifiers, natural unique keys, and upserts so it
can be run repeatedly without duplicating users, roles, profiles, courses,
enrollments, schedules, or deadlines.

## Out of Scope

Phase 5A does not seed conversations, messages, tickets, notifications, events,
question trends, or suggested questions. That activity data belongs to Phase 5B.
