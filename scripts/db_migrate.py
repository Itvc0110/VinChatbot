from __future__ import annotations

import argparse
import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row

from vinchatbot.app.core.config import Settings, get_settings

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MIGRATIONS_DIR = ROOT / "migrations"
MIGRATION_RE = re.compile(r"^(?P<version>\d+)_(?P<name>[A-Za-z0-9][A-Za-z0-9_-]*)\.sql$")

SCHEMA_MIGRATIONS_SQL = """
create table if not exists schema_migrations (
    version integer primary key,
    name text not null,
    checksum text not null,
    applied_at timestamptz not null default now()
);
"""


@dataclass(frozen=True)
class Migration:
    version: int
    name: str
    path: Path
    checksum: str

    @property
    def filename(self) -> str:
        return self.path.name


class MigrationError(RuntimeError):
    """Safe migration error. Messages must never include connection strings."""


def migration_checksum(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_migration_filename(path: Path) -> tuple[int, str]:
    match = MIGRATION_RE.match(path.name)
    if not match:
        raise MigrationError(
            f"Invalid migration filename {path.name!r}; expected NNNNNN_description.sql"
        )
    return int(match.group("version")), match.group("name")


def discover_migrations(migrations_dir: Path = DEFAULT_MIGRATIONS_DIR) -> list[Migration]:
    if not migrations_dir.exists():
        raise MigrationError(f"Migrations directory not found: {migrations_dir}")

    migrations: list[Migration] = []
    seen_versions: set[int] = set()
    for path in sorted(migrations_dir.glob("*.sql")):
        version, name = parse_migration_filename(path)
        if version in seen_versions:
            raise MigrationError(f"Duplicate migration version {version:06d}")
        seen_versions.add(version)
        migrations.append(
            Migration(
                version=version,
                name=name,
                path=path,
                checksum=migration_checksum(path),
            )
        )
    return sorted(migrations, key=lambda migration: migration.version)


def direct_database_url(settings: Settings) -> str:
    url = settings.app_database_url_direct
    if not url:
        raise MigrationError("APP_DATABASE_URL_DIRECT is required for migrations.")
    return url


def ensure_schema_migrations(conn: psycopg.Connection[Any]) -> None:
    conn.execute(SCHEMA_MIGRATIONS_SQL)


def fetch_applied_migrations(conn: psycopg.Connection[Any]) -> dict[int, dict[str, Any]]:
    rows = conn.execute(
        "select version, name, checksum, applied_at from schema_migrations order by version"
    ).fetchall()
    return {int(row["version"]): dict(row) for row in rows}


def validate_applied_checksums(
    migrations: list[Migration],
    applied: dict[int, dict[str, Any]],
) -> None:
    by_version = {migration.version: migration for migration in migrations}
    for version, row in applied.items():
        migration = by_version.get(version)
        if migration is None:
            continue
        if row["checksum"] != migration.checksum:
            raise MigrationError(
                f"Checksum mismatch for migration {migration.filename}; "
                "the file has changed since it was applied."
            )


def pending_migrations(
    migrations: list[Migration],
    applied: dict[int, dict[str, Any]],
) -> list[Migration]:
    validate_applied_checksums(migrations, applied)
    return [migration for migration in migrations if migration.version not in applied]


def connect_direct(settings: Settings) -> psycopg.Connection[Any]:
    return psycopg.connect(
        direct_database_url(settings),
        autocommit=False,
        row_factory=dict_row,
    )


def apply_migration(conn: psycopg.Connection[Any], migration: Migration) -> None:
    sql = migration.path.read_text(encoding="utf-8")
    with conn.transaction():
        conn.execute(sql)
        conn.execute(
            """
            insert into schema_migrations (version, name, checksum)
            values (%s, %s, %s)
            """,
            (migration.version, migration.filename, migration.checksum),
        )


def run_migrations(
    settings: Settings | None = None,
    migrations_dir: Path = DEFAULT_MIGRATIONS_DIR,
) -> int:
    settings = settings or get_settings()
    migrations = discover_migrations(migrations_dir)

    with connect_direct(settings) as conn:
        with conn.transaction():
            ensure_schema_migrations(conn)
        applied = fetch_applied_migrations(conn)
        pending = pending_migrations(migrations, applied)
        if not pending:
            print("No pending migrations")
            return 0

        for migration in pending:
            print(f"Applying {migration.filename}")
            apply_migration(conn, migration)
            print(f"Applied {migration.filename}")

    return len(pending)


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply app database SQL migrations.")
    parser.add_argument(
        "--migrations-dir",
        type=Path,
        default=DEFAULT_MIGRATIONS_DIR,
        help="Directory containing NNNNNN_name.sql migration files.",
    )
    args = parser.parse_args()

    try:
        run_migrations(migrations_dir=args.migrations_dir)
    except MigrationError as exc:
        print(f"Migration failed: {exc}")
        return 1
    except psycopg.Error as exc:
        print(f"Migration failed: database error {type(exc).__name__}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
