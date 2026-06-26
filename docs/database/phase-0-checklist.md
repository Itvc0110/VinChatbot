# Phase 0 Database Checklist

Status is based on manual verification completed before FastAPI database integration.

## Completed

- [x] Neon development branch `dev` created.
- [x] Database `neondb` selected for development.
- [x] Direct connection tested.
- [x] Pooled connection tested.
- [x] Create/drop test table tested.
- [x] `.env.example` updated with safe placeholders.
- [x] Real `.env` is ignored by git and not committed.

## Guardrails

- Do not use the production Neon branch for development or testing.
- Do not commit `.env`.
- Do not print or commit real database URLs, API keys, passwords, or tokens.
- Keep app database settings separate from `POSTGRES_URI`, which may be used by
  LangGraph/checkpointer code.

## Next Phase

Phase 1: add a FastAPI database health endpoint at `/health/db`.
