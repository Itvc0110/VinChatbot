from __future__ import annotations

import argparse

import psycopg

try:
    from scripts.db_migrate import MigrationError, connect_direct
except ModuleNotFoundError:  # pragma: no cover - used when executed as python scripts/db_reset.py
    from db_migrate import MigrationError, connect_direct
from vinchatbot.app.core.config import Settings, get_settings

ALLOWED_RESET_ENVS = {"development", "dev", "local", "test"}


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
            conn.execute("drop table if exists schema_migrations")
    print("Dropped schema_migrations")


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
