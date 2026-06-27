# Phase 4: Base Reference Seed

Phase 4 adds stable reference data only. It is applied through the normal
migration runner:

```bash
python scripts/db_migrate.py
```

Apply this only to the Neon `dev` branch for now.

## Seeded Roles

- `student` — Student
- `institute_admin` — Institute Admin
- `global_admin` — Global Admin
- `staff` — Staff

## Seeded Institutes

- `VIB` — Viện Kinh doanh Quản trị / College of Business and Management
- `CECS` — Viện Kỹ thuật và Khoa học Máy tính / College of Engineering and Computer Science
- `CHS` — Viện Khoa học Sức khỏe / College of Health Sciences
- `CASE` — Viện Khoa học và Giáo dục Khai phóng / College of Arts, Sciences and Education

## Idempotency

The seed migration uses `insert ... on conflict (code) do update`, so it can be
run safely by the migration runner without duplicating role or institute rows.

## Out of Scope

Demo users, 50 student profiles, conversations, tickets, notifications,
schedules, and other sample workflow data are not seeded in this phase. Demo
users are planned for Phase 5.

## Secret Safety

The migration runner uses `APP_DATABASE_URL_DIRECT` internally and never prints
database URLs or credentials.
