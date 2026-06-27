# Phase 2 Migrations

Phase 2 adds a small SQL migration runner and migration tracking table. It does not create
Student Copilot app tables yet.

## Connection Rules

- Migration scripts use `APP_DATABASE_URL_DIRECT`.
- FastAPI runtime continues to use `APP_DATABASE_URL_POOLED`.
- Do not use the pooled URL for migrations, seed scripts, reset tasks, or one-off admin work.
- Do not print, log, or commit database URLs or any other secret values.

## Commands

Apply pending migrations:

```bash
python scripts/db_migrate.py
```

Show applied and pending migrations:

```bash
python scripts/db_status.py
```

Reset app-managed development objects:

```bash
python scripts/db_reset.py --yes
```

The reset command refuses to run unless `APP_ENV` is one of `development`, `dev`, `local`,
or `test`. It also refuses `APP_ENV=production`. In Phase 2, reset only drops the
`schema_migrations` tracking table.

## Tracking Table

The first migration creates only:

```sql
schema_migrations (
    version integer primary key,
    name text not null,
    checksum text not null,
    applied_at timestamptz not null default now()
)
```

## Checksums

Each migration file is hashed with SHA256 before it is applied. The runner stores the checksum
alongside the migration version and filename.

If a migration version has already been applied and the local file checksum changes later, the
runner and status command fail with a safe checksum error. Do not edit applied migrations; add a
new numbered migration instead.
