from __future__ import annotations

from types import SimpleNamespace

import pytest

from scripts import db_migrate, db_reset


def test_parse_migration_filename_accepts_versioned_sql():
    version, name = db_migrate.parse_migration_filename(
        db_migrate.DEFAULT_MIGRATIONS_DIR / "000002_initial_app_schema.sql"
    )

    assert version == 2
    assert name == "initial_app_schema"


def test_discover_migrations_sorts_and_checksums(tmp_path):
    second = tmp_path / "000002_next.sql"
    first = tmp_path / "000001_schema_migrations.sql"
    second.write_text("select 2;", encoding="utf-8")
    first.write_text("select 1;", encoding="utf-8")

    migrations = db_migrate.discover_migrations(tmp_path)

    assert [migration.filename for migration in migrations] == [
        "000001_schema_migrations.sql",
        "000002_next.sql",
    ]
    assert migrations[0].checksum == db_migrate.migration_checksum(first)
    assert len(migrations[0].checksum) == 64


def test_discover_repo_migrations_includes_initial_app_schema():
    migrations = db_migrate.discover_migrations()

    filenames = [migration.filename for migration in migrations]

    assert "000002_initial_app_schema.sql" in filenames
    assert "000003_seed_base_reference_data.sql" in filenames
    assert "000005_admin_notification_workflow.sql" in filenames


def test_admin_notification_workflow_migration_extends_lifecycle_values():
    migration_path = (
        db_migrate.DEFAULT_MIGRATIONS_DIR / "000005_admin_notification_workflow.sql"
    )
    migration_sql = migration_path.read_text(encoding="utf-8").lower()

    assert "notifications_status_check" in migration_sql
    assert "'scheduled'" in migration_sql
    assert "'student_services'" in migration_sql
    assert "create table" not in migration_sql


def test_base_reference_seed_contains_only_roles_and_institutes():
    migration_path = (
        db_migrate.DEFAULT_MIGRATIONS_DIR / "000003_seed_base_reference_data.sql"
    )
    migration_sql = migration_path.read_text(encoding="utf-8")
    migration_sql_lower = migration_sql.lower()

    for role_code in ["student", "institute_admin", "global_admin", "staff"]:
        assert role_code in migration_sql

    for institute_code in ["VIB", "CECS", "CHS", "CASE"]:
        assert institute_code in migration_sql

    assert "insert into roles" in migration_sql_lower
    assert "insert into institutes" in migration_sql_lower
    assert "on conflict (code) do update" in migration_sql_lower
    assert "insert into users" not in migration_sql_lower
    assert "insert into conversations" not in migration_sql_lower
    assert "insert into tickets" not in migration_sql_lower
    assert "insert into notifications" not in migration_sql_lower
    assert "insert into schedules" not in migration_sql_lower


def test_discover_migrations_rejects_duplicate_versions(tmp_path):
    (tmp_path / "000001_one.sql").write_text("select 1;", encoding="utf-8")
    (tmp_path / "000001_two.sql").write_text("select 2;", encoding="utf-8")

    with pytest.raises(db_migrate.MigrationError, match="Duplicate migration version"):
        db_migrate.discover_migrations(tmp_path)


def test_pending_migrations_skips_applied_and_detects_checksum_mismatch(tmp_path):
    first = tmp_path / "000001_schema_migrations.sql"
    second = tmp_path / "000002_next.sql"
    first.write_text("select 1;", encoding="utf-8")
    second.write_text("select 2;", encoding="utf-8")
    migrations = db_migrate.discover_migrations(tmp_path)

    applied = {
        migrations[0].version: {
            "name": migrations[0].filename,
            "checksum": migrations[0].checksum,
        }
    }

    assert db_migrate.pending_migrations(migrations, applied) == [migrations[1]]

    applied[migrations[0].version]["checksum"] = "different"
    with pytest.raises(db_migrate.MigrationError, match="Checksum mismatch"):
        db_migrate.pending_migrations(migrations, applied)


def test_direct_database_url_requires_direct_url_and_ignores_pooled_url():
    settings = SimpleNamespace(
        app_database_url_direct="postgresql://direct.example/neondb",
        app_database_url_pooled="postgresql://pooled.example/neondb",
    )

    assert db_migrate.direct_database_url(settings) == "postgresql://direct.example/neondb"

    with pytest.raises(db_migrate.MigrationError, match="APP_DATABASE_URL_DIRECT"):
        db_migrate.direct_database_url(
            SimpleNamespace(
                app_database_url_direct=None,
                app_database_url_pooled="postgresql://pooled.example/neondb",
            )
        )


def test_reset_environment_guard_allows_only_safe_envs():
    for env in ["development", "dev", "local", "test", " DEVELOPMENT "]:
        db_reset.validate_reset_environment(env)

    with pytest.raises(db_migrate.MigrationError, match="production"):
        db_reset.validate_reset_environment("production")

    with pytest.raises(db_migrate.MigrationError, match="Refusing to reset"):
        db_reset.validate_reset_environment("staging")


def test_reset_requires_yes_before_connecting(monkeypatch):
    def fail_connect(_settings):
        raise AssertionError("reset without --yes must not connect")

    monkeypatch.setattr(db_reset, "connect_direct", fail_connect)

    with pytest.raises(db_migrate.MigrationError, match="--yes"):
        db_reset.reset_app_database(
            SimpleNamespace(
                app_env="development",
                app_database_url_direct="postgresql://direct.example/neondb",
            ),
            yes=False,
        )


def test_reset_tracks_initial_schema_app_objects():
    expected_tables = {
        "users",
        "roles",
        "user_roles",
        "sessions",
        "institutes",
        "student_profiles",
        "courses",
        "enrollments",
        "academic_summaries",
        "schedules",
        "deadlines",
        "notifications",
        "notification_reads",
        "events",
        "conversations",
        "messages",
        "tickets",
        "ticket_messages",
        "ticket_status_history",
        "student_question_events",
        "question_trends",
        "suggested_questions",
        "audit_logs",
        "schema_migrations",
    }

    reset_tables = set(db_reset.APP_MANAGED_TABLES)
    table_order = {
        table: index for index, table in enumerate(db_reset.APP_MANAGED_TABLES)
    }

    assert expected_tables <= reset_tables
    assert "set_updated_at" in db_reset.APP_MANAGED_FUNCTIONS
    assert not {"qdrant", "redis"} & reset_tables
    assert table_order["ticket_messages"] < table_order["tickets"]
    assert table_order["student_profiles"] < table_order["users"]
