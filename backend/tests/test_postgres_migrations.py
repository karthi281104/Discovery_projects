import os

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy.exc import OperationalError
from sqlalchemy import create_engine, inspect


POSTGRES_URL = os.getenv("TEST_POSTGRES_URL")


@pytest.mark.skipif(
    not POSTGRES_URL,
    reason="Set TEST_POSTGRES_URL to a disposable PostgreSQL database to run migration validation",
)
def test_postgres_migrations_upgrade_to_head():
    engine = create_engine(POSTGRES_URL, connect_args={"connect_timeout": 5})
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", POSTGRES_URL)

    try:
        try:
            with engine.connect():
                pass
        except OperationalError as exc:
            pytest.skip(f"PostgreSQL is unavailable at TEST_POSTGRES_URL: {exc}")

        command.upgrade(config, "head")
        inspector = inspect(engine)
        assert {"categories", "locations", "events", "admin_users"} <= set(inspector.get_table_names())
        assert "icon" in {column["name"] for column in inspector.get_columns("categories")}
        event_columns = {column["name"] for column in inspector.get_columns("events")}
        assert {"start_date", "end_date", "registration_url", "is_published"} <= event_columns
    finally:
        engine.dispose()
