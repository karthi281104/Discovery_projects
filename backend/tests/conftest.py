import asyncio
import inspect
from datetime import datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.core.security import create_access_token, hash_password
from app.db.base import Base
from app.db.dependencies import get_db
from app.main import app
from app.models import AdminUser, Category, Event, Location

# Use in-memory SQLite database with StaticPool for fast, isolated testing
TEST_DATABASE_URL = "sqlite:///:memory:"

test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(autouse=True)
def setup_database():
    """Create all tables before each test and drop them after."""
    Base.metadata.create_all(bind=test_engine)
    with TestingSessionLocal() as session:
        # Create default test admin
        admin = AdminUser(
            email=settings.admin_email,
            password_hash=hash_password(settings.admin_password),
            is_active=True,
        )
        session.add(admin)
        session.commit()
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def db():
    """Provide a clean database session for each test."""
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


class AsyncSessionWrapper:
    """Wraps synchronous Session to provide seamless compatibility with both async and sync test code."""

    def __init__(self, session: Session):
        self._session = session

    def add(self, obj):
        return self._session.add(obj)

    def add_all(self, objs):
        return self._session.add_all(objs)

    async def commit(self):
        return self._session.commit()

    async def flush(self):
        return self._session.flush()

    async def execute(self, stmt):
        return self._session.execute(stmt)

    def scalar(self, stmt):
        return self._session.scalar(stmt)

    def scalars(self, stmt):
        return self._session.scalars(stmt)

    def delete(self, obj):
        return self._session.delete(obj)

    def refresh(self, obj):
        return self._session.refresh(obj)

    def __getattr__(self, name):
        return getattr(self._session, name)


@pytest.fixture
def db_session(db):
    """Provides an async-compatible db session fixture for test_critical_acceptance and other tests."""
    return AsyncSessionWrapper(db)


@pytest.fixture
def test_client(client):
    """Provides an alias fixture for client for test_critical_acceptance."""
    return client


@pytest.hookimpl(tryfirst=True)
def pytest_pyfunc_call(pyfuncitem):
    """Executes async coroutine test functions within an event loop if not handled by a plugin."""
    if inspect.iscoroutinefunction(pyfuncitem.obj):
        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            testargs = {arg: pyfuncitem.funcargs[arg] for arg in pyfuncitem._fixtureinfo.argnames}
            loop.run_until_complete(pyfuncitem.obj(**testargs))
            return True
        finally:
            loop.close()
            asyncio.set_event_loop(None)



@pytest.fixture
def client(db):
    """Provide a FastAPI test client with database dependency override."""
    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def admin_token():
    """Return a valid JWT access token for the default admin."""
    return create_access_token(settings.admin_email)


@pytest.fixture
def admin_headers(admin_token):
    """Return authorization headers with Bearer token."""
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture
def sample_category(db):
    cat = Category(
        name="Technology & Hackathons",
        slug="technology-hackathons",
        description="Tech events and hackathons",
        is_active=True,
    )
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return cat


@pytest.fixture
def sample_location(db):
    loc = Location(
        name="Chennai Trade Centre",
        city="Chennai",
        district="Chennai",
        state="Tamil Nadu",
        address="Nandambakkam, Chennai",
        is_active=True,
    )
    db.add(loc)
    db.commit()
    db.refresh(loc)
    return loc


@pytest.fixture
def sample_published_event(db, sample_category, sample_location):
    now = datetime.now(timezone.utc)
    ev = Event(
        title="Chennai Tech Expo 2026",
        slug="chennai-tech-expo-2026",
        short_description="Annual technology summit in Chennai",
        description="The largest gathering of engineers, founders and innovators in Tamil Nadu.",
        organizer_name="Tamil Nadu Tech Council",
        organizer_website="https://example.com/council",
        registration_url="https://example.com/expo/register",
        official_website="https://example.com/expo",
        banner_url="https://example.com/banner.jpg",
        contact_email="expo@example.com",
        event_type="conference",
        mode="offline",
        start_date=now + timedelta(days=10),
        end_date=now + timedelta(days=12),
        registration_deadline=now + timedelta(days=7),
        state="Tamil Nadu",
        district="Chennai",
        city="Chennai",
        venue="Chennai Trade Centre",
        eligibility="Open to all professionals and students",
        participation_fee=500.0,
        currency="INR",
        tags=["tech", "expo", "chennai"],
        status="published",
        is_published=True,
        is_featured=True,
        category_id=sample_category.id,
        location_id=sample_location.id,
    )
    db.add(ev)
    db.commit()
    db.refresh(ev)
    return ev


@pytest.fixture
def sample_draft_event(db, sample_category, sample_location):
    now = datetime.now(timezone.utc)
    ev = Event(
        title="Secret Internal Workshop",
        slug="secret-internal-workshop",
        short_description="Draft workshop not yet approved",
        description="Internal development workshop description.",
        organizer_name="Internal Labs",
        registration_url="https://example.com/workshop",
        event_type="workshop",
        mode="online",
        start_date=now + timedelta(days=5),
        end_date=now + timedelta(days=6),
        status="draft",
        is_published=False,
        is_featured=False,
        category_id=sample_category.id,
        location_id=sample_location.id,
    )
    db.add(ev)
    db.commit()
    db.refresh(ev)
    return ev

