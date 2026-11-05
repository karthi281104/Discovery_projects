from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from app.core.config import settings

engine: Engine = create_engine(settings.database_url, pool_pre_ping=True)


def check_database_connection() -> bool:
    """Return True when the configured database accepts a simple query."""
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    return True
