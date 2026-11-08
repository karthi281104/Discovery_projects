import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch
from sqlalchemy import select

from app.models.models import Event, DiscoverySource, DiscoveredURL, SearchQueryExecution
from app.discovery.service import DiscoveryService
from app.discovery.search import AutonomousSearchEngine


@pytest.mark.asyncio
async def test_critical_acceptance_10_step_autonomous_cycle(db_session, test_client):
    """
    Critical Acceptance Test demonstrating all 10 requirements from Section H:
    1. Start with a minimal source registry (<= 2 sources).
    2. Execute Tamil Nadu search campaign.
    3. Discover unregistered domains via search.
    4. Extract candidates from unregistered websites.
    5. Validate and deduplicate candidates.
    6. Automatically publish valid events with confidence scoring.
    7. Retain complete source evidence and provenance.
    8. Re-run discovery later and detect newly announced events.
    9. Detect changes to previously discovered events.
    10. Verify zero duplicate event records created.
    """

    # -------------------------------------------------------------------------
    # STEP 1: Minimal Seed (< 2 predefined sources)
    # -------------------------------------------------------------------------
    seed_sources = [
        DiscoverySource(
            base_url="https://seed-college.ac.in/events",
            source_type="university",
            extraction_method="jsonld",
            reliability_score=0.8,
            robots_allowed=True,
        ),
        DiscoverySource(
            base_url="https://seed-gov.tn.gov.in/feed.xml",
            source_type="government",
            extraction_method="rss",
            reliability_score=0.9,
            robots_allowed=True,
        ),
    ]
    db_session.add_all(seed_sources)
    await db_session.commit()

    initial_sources_count = (await db_session.execute(select(DiscoverySource))).scalars().all()
    assert len(initial_sources_count) == 2

    # -------------------------------------------------------------------------
    # STEPS 2, 3, 4: Execute Autonomous Search Campaign with Mocked Search/Fetch
    # -------------------------------------------------------------------------
    mock_search_results = [
        {
            "url": "https://unregistered-tn-college.edu.in/symposium-2026",
            "title": "National Technical Symposium 2026 - Chennai",
            "content": "Join our upcoming symposium in Chennai on December 12, 2026.",
        },
        {
            "url": "https://chennai-tech-hub.org/hackathon-2026",
            "title": "Tamil Nadu AI Hackathon 2026",
            "content": "48-hour hackathon happening at T-Hub Chennai on December 20, 2026.",
        },
    ]

    mock_unregistered_page_1 = """
    <html>
      <body>
        <h1>National Technical Symposium 2026</h1>
        <p>Organized by the Department of ECE at Chennai Campus.</p>
        <p>Date: December 12, 2026</p>
        <p>Location: Chennai, Tamil Nadu</p>
        <a href="https://unregistered-tn-college.edu.in/register">Register Online</a>
      </body>
    </html>
    """

    mock_unregistered_page_2 = """
    <html>
      <body>
        <h1>Tamil Nadu AI Hackathon 2026</h1>
        <p>Grand coding marathon across colleges in Tamil Nadu.</p>
        <p>Date: December 20, 2026</p>
        <p>Venue: Guindy Tech Park, Chennai</p>
        <a href="https://chennai-tech-hub.org/join">Apply Now</a>
      </body>
    </html>
    """

    with patch("app.discovery.search.AutonomousSearchEngine.query_searxng", new_callable=AsyncMock) as mock_search, \
         patch("app.discovery.fetcher.fetch_url_content", new_callable=AsyncMock) as mock_fetch, \
         patch("app.discovery.validator.extract_with_ollama", new_callable=AsyncMock) as mock_ollama:

        mock_search.return_value = mock_search_results

        async def fetch_side_effect(url, *args, **kwargs):
            if "unregistered-tn-college" in url:
                return {"html": mock_unregistered_page_1, "status": 200, "headers": {}}
            elif "chennai-tech-hub" in url:
                return {"html": mock_unregistered_page_2, "status": 200, "headers": {}}
            return {"html": "<html><body>None</body></html>", "status": 200, "headers": {}}

        mock_fetch.side_effect = fetch_side_effect

        # Dynamic mock function that matches content instead of exhausting an iterator
        async def ollama_side_effect(text, *args, **kwargs):
            if "National Technical Symposium" in text:
                return {
                    "is_event": True,
                    "title": "National Technical Symposium 2026",
                    "start_date": "2026-12-12T09:00:00",
                    "end_date": "2026-12-12T17:00:00",
                    "venue_name": "Department of ECE, Chennai Campus",
                    "city": "Chennai",
                    "organizer": "Unregistered TN College",
                    "registration_url": "https://unregistered-tn-college.edu.in/register",
                    "verbatim_evidence_quote": "Organized by the Department of ECE at Chennai Campus. Date: December 12, 2026",
                }
            elif "Tamil Nadu AI Hackathon" in text:
                return {
                    "is_event": True,
                    "title": "Tamil Nadu AI Hackathon 2026",
                    "start_date": "2026-12-20T10:00:00",
                    "end_date": "2026-12-21T18:00:00",
                    "venue_name": "Guindy Tech Park",
                    "city": "Chennai",
                    "organizer": "Chennai Tech Hub",
                    "registration_url": "https://chennai-tech-hub.org/join",
                    "verbatim_evidence_quote": "Grand coding marathon across colleges in Tamil Nadu. Date: December 20, 2026",
                }
            return {
                "is_event": False,
                "title": None,
                "start_date": None,
                "end_date": None,
                "venue_name": None,
                "city": None,
                "organizer": None,
                "registration_url": None,
                "verbatim_evidence_quote": None,
            }

        mock_ollama.side_effect = ollama_side_effect

        # Execute Run 1: Autonomous Search Campaign
        service = DiscoveryService(db_session)
        run_1_metrics = await service.run_autonomous_campaign(
            region="Tamil Nadu",
            categories=["Hackathon", "Symposium"],
            languages=["en", "ta"],
        )

    # -------------------------------------------------------------------------
    # STEPS 3 & 4 VERIFICATION: Discovered Sources and Candidate Processing
    # -------------------------------------------------------------------------
    assert run_1_metrics["queries_executed"] > 0
    assert run_1_metrics["search_results_collected"] >= 2
    assert run_1_metrics["new_urls_discovered"] >= 2
    assert run_1_metrics["new_sources_identified"] >= 2
    assert run_1_metrics["event_candidates_extracted"] == 2

    # Verify newly registered sources were saved to database
    all_sources = (await db_session.execute(select(DiscoverySource))).scalars().all()
    assert len(all_sources) >= 4  # 2 seeds + 2 newly discovered sources

    # -------------------------------------------------------------------------
    # STEPS 5, 6, 7 VERIFICATION: Auto-Publishing and Full Provenance Evidence
    # -------------------------------------------------------------------------
    assert run_1_metrics["valid_events"] == 2
    assert run_1_metrics["events_published"] == 2
    assert run_1_metrics["duplicates_detected"] == 0

    published_events = (
        await db_session.execute(select(Event).where(Event.validation_outcome == "auto_published"))
    ).scalars().all()
    assert len(published_events) == 2

    for event in published_events:
        assert event.original_source_url is not None
        assert event.discovered_at is not None
        assert event.extracted_at is not None
        assert event.verified_at is not None
        assert event.confidence_score >= 0.80
        assert event.content_hash is not None
        assert event.update_history == []

    # -------------------------------------------------------------------------
    # STEPS 8, 9, 10: Run 2 - Detect Changes, Cross-Domain Duplicates & New Events
    # -------------------------------------------------------------------------
    # Scenario:
    # 1. Page 1 (Symposium) changed venue to "Main Auditorium Hall A"
    # 2. A 3rd domain cross-posts the Hackathon (cross-source duplicate)
    # 3. A brand-new event is posted on an already discovered source

    mock_search_results_run_2 = [
        {
            "url": "https://unregistered-tn-college.edu.in/symposium-2026",
            "title": "National Technical Symposium 2026 - Chennai",
            "content": "Venue updated to Main Auditorium Hall A.",
        },
        {
            "url": "https://events-aggregator-tn.in/hackathon-2026",
            "title": "Tamil Nadu AI Hackathon 2026",
            "content": "Mirrored listing of the Tamil Nadu AI Hackathon.",
        },
        {
            "url": "https://unregistered-tn-college.edu.in/workshop-iot",
            "title": "State-Level IoT & Edge AI Workshop 2026",
            "content": "Hands-on workshop on December 28, 2026.",
        },
    ]

    with patch("app.discovery.search.AutonomousSearchEngine.query_searxng", new_callable=AsyncMock) as mock_search_2, \
         patch("app.discovery.fetcher.fetch_url_content", new_callable=AsyncMock) as mock_fetch_2, \
         patch("app.discovery.validator.extract_with_ollama", new_callable=AsyncMock) as mock_ollama_2:

        mock_search_2.return_value = mock_search_results_run_2

        async def fetch_side_effect_2(url, *args, **kwargs):
            if "symposium-2026" in url:
                return {
                    "html": "<html><body><h1>National Technical Symposium 2026</h1><p>Venue: Main Auditorium Hall A</p><p>Date: December 12, 2026</p></body></html>",
                    "status": 200,
                    "headers": {},
                }
            elif "events-aggregator-tn" in url:
                return {
                    "html": "<html><body><h1>Tamil Nadu AI Hackathon 2026</h1><p>Date: December 20, 2026</p><p>Venue: Guindy Tech Park</p></body></html>",
                    "status": 200,
                    "headers": {},
                }
            elif "workshop-iot" in url:
                return {
                    "html": "<html><body><h1>State-Level IoT & Edge AI Workshop 2026</h1><p>Date: December 28, 2026</p><p>Venue: Chennai</p></body></html>",
                    "status": 200,
                    "headers": {},
                }
            return {"html": "", "status": 404, "headers": {}}

        mock_fetch_2.side_effect = fetch_side_effect_2

        async def ollama_side_effect_2(text, *args, **kwargs):
            if "National Technical Symposium" in text:
                return {
                    "is_event": True,
                    "title": "National Technical Symposium 2026",
                    "start_date": "2026-12-12T09:00:00",
                    "end_date": "2026-12-12T17:00:00",
                    "venue_name": "Main Auditorium Hall A",
                    "city": "Chennai",
                    "organizer": "Unregistered TN College",
                    "registration_url": "https://unregistered-tn-college.edu.in/register",
                    "verbatim_evidence_quote": "Venue: Main Auditorium Hall A. Date: December 12, 2026",
                }
            elif "Tamil Nadu AI Hackathon" in text:
                return {
                    "is_event": True,
                    "title": "Tamil Nadu AI Hackathon 2026",
                    "start_date": "2026-12-20T10:00:00",
                    "end_date": "2026-12-21T18:00:00",
                    "venue_name": "Guindy Tech Park",
                    "city": "Chennai",
                    "organizer": "Chennai Tech Hub",
                    "registration_url": "https://chennai-tech-hub.org/join",
                    "verbatim_evidence_quote": "Mirrored listing. Date: December 20, 2026",
                }
            elif "IoT & Edge AI Workshop" in text:
                return {
                    "is_event": True,
                    "title": "State-Level IoT & Edge AI Workshop 2026",
                    "start_date": "2026-12-28T09:30:00",
                    "end_date": "2026-12-28T16:30:00",
                    "venue_name": "Seminar Hall 2",
                    "city": "Chennai",
                    "organizer": "Unregistered TN College",
                    "registration_url": "https://unregistered-tn-college.edu.in/workshop-iot",
                    "verbatim_evidence_quote": "Hands-on workshop on December 28, 2026 at Seminar Hall 2, Chennai",
                }
            return {
                "is_event": False,
                "title": None,
                "start_date": None,
                "end_date": None,
                "venue_name": None,
                "city": None,
                "organizer": None,
                "registration_url": None,
                "verbatim_evidence_quote": None,
            }

        mock_ollama_2.side_effect = ollama_side_effect_2

        run_2_metrics = await service.run_autonomous_campaign(
            region="Tamil Nadu",
            categories=["Hackathon", "Symposium", "Workshop"],
            languages=["en", "ta"],
        )

    # -------------------------------------------------------------------------
    # FINAL STEP VERIFICATIONS: Zero duplicates, exactly 1 updated, 1 new event
    # -------------------------------------------------------------------------
    assert run_2_metrics["events_updated"] == 1
    assert run_2_metrics["duplicates_detected"] >= 1
    assert run_2_metrics["events_published"] == 1  # Only the IoT workshop was newly published

    # Total published events should now be exactly 3 (2 from Run 1 + 1 new from Run 2)
    total_published = (
        await db_session.execute(select(Event).where(Event.validation_outcome == "auto_published"))
    ).scalars().all()
    assert len(total_published) == 3

    # Verify event update audit log on Symposium
    symposium = next(e for e in total_published if "Symposium" in e.title)
    assert symposium.venue_name == "Main Auditorium Hall A"
    assert len(symposium.update_history) >= 1
    assert symposium.update_history[0]["field"] == "venue_name"
    assert symposium.update_history[0]["old_value"] == "Department of ECE, Chennai Campus"
    assert symposium.update_history[0]["new_value"] == "Main Auditorium Hall A"

    # Verify cross-domain duplicate URL retention on Hackathon
    hackathon = next(e for e in total_published if "Hackathon" in e.title)
    assert "https://events-aggregator-tn.in/hackathon-2026" in hackathon.additional_source_urls