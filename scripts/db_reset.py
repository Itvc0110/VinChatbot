from __future__ import annotations

import argparse

import psycopg
from psycopg import sql

try:
    from scripts.db_migrate import MigrationError, connect_direct
except ModuleNotFoundError:  # pragma: no cover - used when executed as python scripts/db_reset.py
    from db_migrate import MigrationError, connect_direct
from vinchatbot.app.core.config import Settings, get_settings

ALLOWED_RESET_ENVS = {"development", "dev", "local", "test"}
APP_MANAGED_TABLES = (
    "audit_logs",
    "suggested_questions",
    "question_trends",
    "student_question_events",
    "ticket_status_history",
    "ticket_messages",
    "tickets",
    "messages",
    "conversations",
    "events",
    "notification_reads",
    "notifications",
    "deadlines",
    "schedules",
    "academic_summaries",
    "enrollments",
    "courses",
    "student_profiles",
    "institutes",
    "sessions",
    "user_roles",
    "roles",
    "users",
    "schema_migrations",
)
APP_MANAGED_FUNCTIONS = ("set_updated_at",)
APP_MANAGED_TYPES: tuple[str, ...] = ()


def validate_reset_environment(app_env: str) -> None:
    env = (app_env or "").strip().lower()
    if env == "production":
        raise MigrationError("Refusing to reset the app database when APP_ENV=production.")
    if env not in ALLOWED_RESET_ENVS:
        allowed = ", ".join(sorted(ALLOWED_RESET_ENVS))
        raise MigrationError(f"Refusing to reset the app database for APP_ENV={env!r}; allowed: {allowed}.")


def reset_app_database(settings: Settings | None = None, *, yes: bool = False) -> None:
    settings = settings or get_settings()
    validate_reset_environment(settings.app_env)
    if not yes:
        raise MigrationError("Reset requires --yes.")

    with connect_direct(settings) as conn:
        with conn.transaction():
            for table in APP_MANAGED_TABLES:
                conn.execute(
                    sql.SQL("drop table if exists {}").format(sql.Identifier(table))
                )
            for type_name in APP_MANAGED_TYPES:
                conn.execute(
                    sql.SQL("drop type if exists {}").format(sql.Identifier(type_name))
                )
            for function_name in APP_MANAGED_FUNCTIONS:
                conn.execute(
                    sql.SQL("drop function if exists {}()").format(
                        sql.Identifier(function_name)
                    )
                )
    print("Dropped app-managed database objects")


def main() -> int:
    parser = argparse.ArgumentParser(description="Reset app-managed development database objects.")
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Confirm destructive reset of app-managed objects.",
    )
    args = parser.parse_args()

    if args.yes:
        print("Resetting app-managed database objects for non-production environment.")
    else:
        print("Reset would drop app-managed database objects. Re-run with --yes to proceed.")

    try:
        reset_app_database(yes=args.yes)
    except MigrationError as exc:
        print(f"Database reset failed: {exc}")
        return 1
    except psycopg.Error as exc:
        print(f"Database reset failed: database error {type(exc).__name__}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
