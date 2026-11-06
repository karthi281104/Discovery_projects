from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock
import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import engine
from app.discovery.service import (
    expire_past_events,
    run_all_enabled_sources,
    run_discovery_for_source,
)
from app.models import Category, DiscoveryRun, DiscoverySource, Event, EventSource, Location
from app.services import list_events


@pytest.fixture
def db_session():
    with Session(engine) as session:
        yield session


@pytest.fixture
def sample_source(db_session):
    source = db_session.scalar(
        select(DiscoverySource).where(DiscoverySource.name == "Pipeline Test RSS Source")
    )
    if not source:
        source = DiscoverySource(
            name="Pipeline Test RSS Source",
            base_url="https://example.com/test-pipeline-rss.xml",
            source_type="rss",
            region="Tamil Nadu",
            is_enabled=True,
            crawl_interval=60,
        )
        db_session.add(source)
        db_session.commit()
        db_session.refresh(source)
    return source


@pytest.mark.anyio
async def test_end_to_end_discovery_pipeline_and_auto_publishing(sample_source, db_session):
    # Ensure clean slate for test event
    existing_events = db_session.scalars(
        select(Event).where(Event.title.like("%Salem Open Source AI Hackathon%"))
    ).all()
    for ev in existing_events:
        db_session.delete(ev)
    db_session.commit()

    now = datetime.now(timezone.utc)
    start_time = now + timedelta(days=15)
    start_str = start_time.strftime("%Y-%m-%dT%H:%M:%SZ")

    sample_rss = f"""<?xml version="1.0" encoding="utf-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom">
        <title>Tamil Nadu Tech Events</title>
        <entry>
            <title>Salem Open Source AI Hackathon 2026</title>
            <link href="https://example.com/events/salem-ai-2026"/>
            <id>salem-ai-2026-v1</id>
            <published>{start_str}</published>
            <summary>A premier 24-hour hackathon for building regional AI applications in Salem, Tamil Nadu.</summary>
            <author><name>Salem Tech Forum</name></author>
            <category term="hackathon"/>
        </entry>
    </feed>"""

    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.text = sample_rss
    mock_fetcher = AsyncMock()
    mock_fetcher.fetch.return_value = mock_resp

    # 1. First Run -> Event Created and Auto-Published
    run1 = await run_discovery_for_source(db_session, sample_source.id, mock_fetcher)
    assert run1.status == "success"
    assert run1.events_created == 1
    assert run1.duplicates_skipped == 0
    assert run1.events_updated == 0

    # Verify event exists in DB and is published
    event = db_session.scalar(select(Event).where(Event.title == "Salem Open Source AI Hackathon 2026"))
    assert event is not None
    assert event.status == "published"
    assert event.is_published is True
    assert event.city == "Salem"
    assert event.organizer_name == "Salem Tech Forum"

    # Verify event appears through public list_events API without any manual approval!
    pub_events, total = list_events(db_session, search="Salem Open Source", published_only=True)
    assert total >= 1
    assert any(e.id == event.id for e in pub_events)

    # Verify EventSource link
    ev_source = db_session.scalar(select(EventSource).where(EventSource.event_id == event.id))
    assert ev_source is not None
    assert ev_source.source_id == sample_source.id

    # 2. Second Run with Same Content -> Idempotent, Skipped
    run2 = await run_discovery_for_source(db_session, sample_source.id, mock_fetcher)
    assert run2.status == "success"
    assert run2.events_created == 0
    assert run2.duplicates_skipped == 1
    assert run2.events_updated == 0

    # 3. Third Run with Changed Date -> Updated Safely
    updated_start = start_time + timedelta(days=2)
    updated_start_str = updated_start.strftime("%Y-%m-%dT%H:%M:%SZ")

    updated_rss = f"""<?xml version="1.0" encoding="utf-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom">
        <title>Tamil Nadu Tech Events</title>
        <entry>
            <title>Salem Open Source AI Hackathon 2026</title>
            <link href="https://example.com/events/salem-ai-2026"/>
            <id>salem-ai-2026-v1</id>
            <published>{updated_start_str}</published>
            <summary>A premier 24-hour hackathon for building regional AI applications in Salem, Tamil Nadu.</summary>
            <author><name>Salem Tech Forum</name></author>
            <category term="hackathon"/>
        </entry>
    </feed>"""

    mock_resp.text = updated_rss
    run3 = await run_discovery_for_source(db_session, sample_source.id, mock_fetcher)
    assert run3.status == "success"
    assert run3.events_updated == 1
    assert run3.events_created == 0

    # 4. Source Error Isolation
    mock_fetcher.fetch.side_effect = Exception("Simulated connection timeout")
    run_err = await run_discovery_for_source(db_session, sample_source.id, mock_fetcher)
    assert run_err.status == "failed"
    assert "Simulated connection timeout" in (run_err.error_message or "")


def test_expire_past_events(db_session):
    past_date = datetime.now(timezone.utc) - timedelta(days=2)
    slug = f"past-expired-test-event-{int(past_date.timestamp())}"
    cat = db_session.scalars(select(Category)).first()
    loc = db_session.scalars(select(Location)).first()

    past_event = Event(
        title="Expired Event Test",
        slug=slug,
        description="Event that finished two days ago.",
        start_date=past_date,
        end_date=past_date,
        starts_at=past_date,
        ends_at=past_date,
        registration_url="https://example.com/past",
        organizer_name="Old Organizer",
        status="published",
        is_published=True,
        category_id=cat.id if cat else 1,
        location_id=loc.id if loc else 1,
    )
    db_session.add(past_event)
    db_session.commit()

    count = expire_past_events(db_session)
    assert count >= 1

    db_session.refresh(past_event)
    assert past_event.status == "expired"
    assert past_event.is_published is False
