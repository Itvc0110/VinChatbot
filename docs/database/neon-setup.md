# Neon Setup

Phase 0 prepares the app database configuration only. It does not add schema, migrations,
authentication, tickets, conversations, or database runtime wiring.

## Development Database

- Neon branch: `dev`
- Database: `neondb`
- Direct URL: use for migrations, seed scripts, reset tasks, and one-off admin work.
- Pooled URL: use for FastAPI runtime connections.

Do not use the production branch for development or testing. Do not commit `.env` or any real
database URL, API key, password, token, or connection string.

## Environment Variables

Use masked placeholders in shared docs and examples:

```bash
APP_DATABASE_URL_DIRECT="postgresql://USER:PASSWORD@HOST.neon.tech/neondb?sslmode=require"
APP_DATABASE_URL_POOLED="postgresql://USER:PASSWORD@HOST-pooler.neon.tech/neondb?sslmode=require"
APP_DATABASE_POOL_MIN_SIZE=1
APP_DATABASE_POOL_MAX_SIZE=5
```

Real values belong only in local `.env`, which is ignored by git.

## Manual Smoke Tests

Load local environment variables without printing them:

```bash
set -a
source .env
set +a
```

Test the direct connection:

```bash
python - <<'PY'
import os
import psycopg

with psycopg.connect(os.environ["APP_DATABASE_URL_DIRECT"]) as conn:
    with conn.cursor() as cur:
        cur.execute("select 1")
        cur.fetchone()

print("direct connection ok")
PY
```

Test the pooled connection:

```bash
python - <<'PY'
import os
import psycopg

with psycopg.connect(os.environ["APP_DATABASE_URL_POOLED"]) as conn:
    with conn.cursor() as cur:
        cur.execute("select 1")
        cur.fetchone()

print("pooled connection ok")
PY
```

Optional create/drop smoke test, using the direct URL:

```bash
python - <<'PY'
import os
import psycopg

with psycopg.connect(os.environ["APP_DATABASE_URL_DIRECT"]) as conn:
    with conn.cursor() as cur:
        cur.execute("create table if not exists phase0_smoke_test (id int primary key)")
        cur.execute("drop table phase0_smoke_test")

print("create/drop smoke test ok")
PY
```

These tests intentionally print only success messages, never connection strings.
