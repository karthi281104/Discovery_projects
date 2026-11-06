import os
from datetime import datetime, timezone
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import OperationalError

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ALEMBIC_INI = os.path.join(BACKEND_DIR, "alembic.ini")
MIGRATIONS_DIR = os.path.join(BACKEND_DIR, "migrations")

POSTGRES_URL = os.getenv("TEST_POSTGRES_URL")
IS_CI = os.getenv("CI") == "true" or os.getenv("GITHUB_ACTIONS") == "true"


def get_postgres_engine():
    if not POSTGRES_URL:
        if IS_CI:
            pytest.fail("TEST_POSTGRES_URL environment variable must be set in CI.")
        pytest.skip("Set TEST_POSTGRES_URL to run PostgreSQL migration validation")

    engine = create_engine(POSTGRES_URL, connect_args={"connect_timeout": 5})
    try:
        with engine.connect():
            pass
    except OperationalError as exc:
        if IS_CI:
            pytest.fail(f"PostgreSQL service must be reachable in CI at TEST_POSTGRES_URL: {exc}")
        pytest.skip(f"PostgreSQL is unavailable at TEST_POSTGRES_URL: {exc}")
    return engine


def get_alembic_config(db_url: str) -> Config:
    config = Config(ALEMBIC_INI)
    config.set_main_option("script_location", MIGRATIONS_DIR)
    config.set_main_option("sqlalchemy.url", db_url)
    return config


def test_sqlite_migrations_lifecycle_and_data_preservation(tmp_path):
    """
    Validate that Alembic migrations run cleanly against SQLite,
    preserving pre-existing records across all revisions (0001 to head),
    and can downgrade to base and re-upgrade without schema drift.
    """
    db_file = tmp_path / "migration_lifecycle_test.db"
    db_url = f"sqlite:///{db_file.as_posix()}"
    engine = create_engine(db_url)
    config = get_alembic_config(db_url)

    try:
        # 1. Upgrade to 0001_initial
        command.upgrade(config, "0001_initial")
        now = datetime.now(timezone.utc)
        with engine.begin() as conn:
            conn.execute(text("""
                INSERT INTO categories (id, name, slug, description)
                VALUES (1, 'Legacy Category', 'legacy-category', 'Initial category')
            """))
            conn.execute(text("""
                INSERT INTO locations (id, name, city, state, address)
                VALUES (1, 'Legacy Venue', 'Chennai', 'Tamil Nadu', 'Legacy Road, Chennai')
            """))
            conn.execute(text("""
                INSERT INTO events (
                    id, title, description, starts_at, ends_at, organizer, ticket_url,
                    image_url, is_published, category_id, location_id, created_at, updated_at
                ) VALUES (
                    10, 'Pre-existing Legacy Event', 'Detailed legacy description',
                    :starts_at, :ends_at, 'Original Organizer', 'https://example.com/tickets',
                    'https://example.com/banner.jpg', 1, 1, 1, :created_at, :updated_at
                )
            """), {
                "starts_at": now.isoformat(),
                "ends_at": now.isoformat(),
                "created_at": now.isoformat(),
                "updated_at": now.isoformat(),
            })

        # 2. Upgrade to head across all versions
        command.upgrade(config, "head")

        inspector = inspect(engine)
        tables = set(inspector.get_table_names())
        assert {"categories", "locations", "events", "admin_users", "alembic_version"} <= tables

        loc_cols = {c["name"] for c in inspector.get_columns("locations")}
        assert "is_verified_venue" in loc_cols

        with engine.connect() as conn:
            row = conn.execute(text("""
                SELECT id, title, slug, organizer_name, registration_url, banner_url,
                       start_date, status, is_published, is_featured, currency
                FROM events WHERE id = 10
            """)).mappings().one()

            assert row["title"] == "Pre-existing Legacy Event"
            assert row["slug"] == "event-10"
            assert row["organizer_name"] == "Original Organizer"
            assert row["registration_url"] == "https://example.com/tickets"
            assert row["banner_url"] == "https://example.com/banner.jpg"
            assert row["start_date"] is not None
            assert row["status"] == "published"
            assert row["is_published"] in (True, 1)
            assert row["is_featured"] in (False, 0)
            assert row["currency"] == "INR"

        # 3. Test downgrade to base
        command.downgrade(config, "base")
        inspector_empty = inspect(engine)
        remaining = set(inspector_empty.get_table_names()) - {"alembic_version"}
        assert len(remaining) == 0

        # 4. Re-upgrade from base to head
        command.upgrade(config, "head")
        inspector_fresh = inspect(engine)
        assert {"categories", "locations", "events", "admin_users"} <= set(inspector_fresh.get_table_names())
    finally:
        engine.dispose()


def test_postgres_fresh_installation_upgrade_downgrade():
    engine = get_postgres_engine()
    config = get_alembic_config(POSTGRES_URL)

    try:
        # Clean slate: downgrade to base then upgrade to head
        command.downgrade(config, "base")
        command.upgrade(config, "head")

        inspector = inspect(engine)
        tables = set(inspector.get_table_names())
        assert {"categories", "locations", "events", "admin_users", "alembic_version"} <= tables

        cat_cols = {c["name"] for c in inspector.get_columns("categories")}
        assert {"id", "name", "slug", "description", "icon", "is_active"} <= cat_cols

        loc_cols = {c["name"] for c in inspector.get_columns("locations")}
        assert {"id", "name", "city", "district", "state", "address", "is_active", "is_verified_venue"} <= loc_cols

        event_cols = {c["name"] for c in inspector.get_columns("events")}
        expected_event_cols = {
            "id", "title", "slug", "short_description", "description",
            "start_date", "end_date", "registration_deadline", "organizer_name",
            "registration_url", "official_website", "banner_url", "contact_email",
            "event_type", "mode", "status", "city", "district", "venue", "state",
            "eligibility", "participation_fee", "currency", "tags",
            "is_published", "is_featured", "category_id", "location_id",
            "created_at", "updated_at",
        }
        assert expected_event_cols <= event_cols

        event_indexes = {idx["name"] for idx in inspector.get_indexes("events")}
        assert {
            "ix_events_slug", "ix_events_start_date", "ix_events_status",
            "ix_events_category_id", "ix_events_location_id",
        } <= event_indexes

        # Test downgrade to base and re-upgrade
        command.downgrade(config, "base")
        inspector_empty = inspect(engine)
        remaining = set(inspector_empty.get_table_names()) - {"alembic_version"}
        assert len(remaining) == 0

        command.upgrade(config, "head")
    finally:
        engine.dispose()


def test_postgres_migration_with_existing_records_data_preservation():
    engine = get_postgres_engine()
    config = get_alembic_config(POSTGRES_URL)

    try:
        # Start at 0001_initial
        command.downgrade(config, "base")
        command.upgrade(config, "0001_initial")

        # Insert legacy data into 0001 schema
        now = datetime.now(timezone.utc)
        with engine.begin() as conn:
            conn.execute(text("""
                INSERT INTO categories (id, name, slug, description)
                VALUES (1, 'Legacy Category', 'legacy-category', 'Initial category')
            """))
            conn.execute(text("""
                INSERT INTO locations (id, name, city, state, address)
                VALUES (1, 'Legacy Venue', 'Chennai', 'Tamil Nadu', 'Legacy Road, Chennai')
            """))
            conn.execute(text("""
                INSERT INTO events (
                    id, title, description, starts_at, ends_at, organizer, ticket_url,
                    image_url, is_published, category_id, location_id, created_at, updated_at
                ) VALUES (
                    10, 'Pre-existing Legacy Event', 'Detailed legacy description',
                    :starts_at, :ends_at, 'Original Organizer', 'https://example.com/tickets',
                    'https://example.com/banner.jpg', TRUE, 1, 1, :created_at, :updated_at
                )
            """), {
                "starts_at": now,
                "ends_at": now,
                "created_at": now,
                "updated_at": now,
            })

        # Upgrade through all migrations to head
        command.upgrade(config, "head")

        # Verify data preservation and column backfill in head
        with engine.connect() as conn:
            row = conn.execute(text("""
                SELECT id, title, slug, organizer_name, registration_url, banner_url,
                       start_date, status, is_published, is_featured, currency
                FROM events WHERE id = 10
            """)).mappings().one()

            assert row["title"] == "Pre-existing Legacy Event"
            assert row["slug"] == "event-10"
            assert row["organizer_name"] == "Original Organizer"
            assert row["registration_url"] == "https://example.com/tickets"
            assert row["banner_url"] == "https://example.com/banner.jpg"
            assert row["start_date"] is not None
            assert row["status"] == "published"
            assert row["is_published"] is True
            assert row["is_featured"] is False
            assert row["currency"] == "INR"
    finally:
        engine.dispose()
