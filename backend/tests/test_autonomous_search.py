from unittest.mock import AsyncMock

import pytest

from app.core.config import settings
from app.discovery.search import SearchHit, build_queries, run_search_campaign
from app.models import DiscoverySource, Event
from sqlalchemy import select


def test_query_generation_covers_region_and_languages():
    queries = build_queries(region="Tamil Nadu", languages=("en", "ta"))
    assert any("Tamil Nadu" in query for query in queries)
    assert any("தமிழ்நாடு" in query for query in queries)
    assert len(queries) == len(set(queries))


@pytest.mark.anyio
async def test_search_campaign_registers_unknown_source_and_pipeline_publishes(db, monkeypatch):
    monkeypatch.setattr(settings, "discovery_search_url", "http://searxng.test")
    monkeypatch.setattr(settings, "discovery_search_max_queries", 1)

    async def fake_search(*args, **kwargs):
        return [
            SearchHit(
                url="https://new-organizer.example/events/chennai-open-source-day",
                title="Chennai Open Source Day 2026",
                snippet="Register for an open source event in Tamil Nadu.",
                score=0.8,
            )
        ]

    monkeypatch.setattr("app.discovery.search.search_searxng", fake_search)
    html = """<article class="event-card">
      <h2>Chennai Open Source Day 2026</h2>
      <time datetime="2026-12-10T10:00:00+05:30">10 December 2026</time>
      <p>Join developers for a full day of open source talks and contribution workshops in Chennai.</p>
      <a href="https://new-organizer.example/register">Register</a>
    </article>"""
    fetcher = AsyncMock()
    fetcher.fetch.return_value.text = html
    campaign = await run_search_campaign(db, fetcher=fetcher)
    assert campaign.status == "success"
    assert campaign.sources_discovered == 1

    source = db.scalar(
        select(DiscoverySource).where(
            DiscoverySource.base_url == "https://new-organizer.example/events/chennai-open-source-day"
        )
    )
    assert source is not None
    assert source.source_type == "auto"

    event = db.scalar(select(Event).where(Event.title == "Chennai Open Source Day 2026"))
    assert event is not None
    assert event.is_published is True
