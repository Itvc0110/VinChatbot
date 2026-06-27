from __future__ import annotations

import argparse
from pathlib import Path

import psycopg

try:
    from scripts.db_migrate import (
        DEFAULT_MIGRATIONS_DIR,
        MigrationError,
        connect_direct,
        discover_migrations,
        ensure_schema_migrations,
        fetch_applied_migrations,
        pending_migrations,
    )
except ModuleNotFoundError:  # pragma: no cover - used when executed as python scripts/db_status.py
    from db_migrate import (
        DEFAULT_MIGRATIONS_DIR,
        MigrationError,
        connect_direct,
        discover_migrations,
        ensure_schema_migrations,
        fetch_applied_migrations,
        pending_migrations,
    )
from vinchatbot.app.core.config import get_settings


def print_migration_status(migrations_dir: Path = DEFAULT_MIGRATIONS_DIR) -> None:
    migrations = discover_migrations(migrations_dir)
    settings = get_settings()

    with connect_direct(settings) as conn:
        with conn.transaction():
            ensure_schema_migrations(conn)
        applied = fetch_applied_migrations(conn)
        pending = pending_migrations(migrations, applied)

    print("Applied migrations:")
    if applied:
        for version in sorted(applied):
            row = applied[version]
            print(f"  {version:06d} {row['name']} applied_at={row['applied_at']}")
    else:
        print("  none")

    print("Pending migrations:")
    if pending:
        for migration in pending:
            print(f"  {migration.filename}")
    else:
        print("  none")


def main() -> int:
    parser = argparse.ArgumentParser(description="Show app database migration status.")
    parser.add_argument(
        "--migrations-dir",
        type=Path,
        default=DEFAULT_MIGRATIONS_DIR,
        help="Directory containing NNNNNN_name.sql migration files.",
    )
    args = parser.parse_args()

    try:
        print_migration_status(args.migrations_dir)
    except MigrationError as exc:
        print(f"Migration status failed: {exc}")
        return 1
    except psycopg.Error as exc:
        print(f"Migration status failed: database error {type(exc).__name__}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
