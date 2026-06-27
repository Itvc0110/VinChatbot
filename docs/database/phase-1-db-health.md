# Phase 1 Database Health

Phase 1 adds the FastAPI application database pool and a database readiness endpoint.
It does not add schema, migrations, authentication, tickets, conversations, or seed data.

## Runtime Connection

- FastAPI runtime uses `APP_DATABASE_URL_POOLED` when it is configured.
- `APP_DATABASE_URL_DIRECT` remains reserved for future migrations, seed scripts, reset tasks,
  and one-off admin work.
- If the pooled URL is missing, runtime falls back to the direct URL.
- If neither URL is configured, application startup remains safe, but `/health/db` returns
  HTTP 503.

Never expose, log, or commit database URLs, passwords, API keys, tokens, or connection strings.

## Endpoint

```bash
curl http://localhost:8000/health/db
```

Successful response shape:

```json
{
  "status": "ok",
  "database": "neondb",
  "user": "app_user",
  "provider": "neon",
  "latency_ms": 12.34,
  "version": "PostgreSQL ..."
}
```

Unavailable response shape:

```json
{
  "detail": {
    "status": "unavailable",
    "reason": "app database is not configured"
  }
}
```

The endpoint intentionally returns metadata only. It must never return the configured database URL
or any secret value.
