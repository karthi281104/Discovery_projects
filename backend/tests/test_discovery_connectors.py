from unittest.mock import AsyncMock, MagicMock
import httpx
import pytest

from app.discovery.connectors.api import APIConnector
from app.discovery.connectors.html import HTMLConnector
from app.discovery.connectors.jsonld import JsonLdConnector
from app.discovery.connectors.registry import get_connector
from app.discovery.connectors.rss import RSSConnector
from app.models import DiscoverySource


@pytest.mark.anyio
async def test_rss_connector():
    rss_xml = """<?xml version="1.0" encoding="utf-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom">
        <title>Tamil Nadu Tech Events</title>
        <entry>
            <title>Chennai Python Meetup November 2026</title>
            <link href="https://example.com/events/chennai-python-nov-2026"/>
            <id>urn:uuid:12345</id>
            <published>2026-11-25T10:00:00Z</published>
            <summary>Monthly meetup covering FastAPI, async Python, and regional AI projects.</summary>
            <author><name>ChennaiPy Community</name></author>
            <category term="python"/>
            <category term="fastapi"/>
        </entry>
    </feed>"""

    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.text = rss_xml

    mock_fetcher = AsyncMock()
    mock_fetcher.fetch.return_value = mock_resp

    source = DiscoverySource(
        id=1,
        name="Test RSS",
        base_url="https://example.com/rss",
        source_type="rss",
    )

    connector = RSSConnector()
    candidates = await connector.extract_candidates(source, mock_fetcher)

    assert len(candidates) == 1
    c = candidates[0]
    assert c.title == "Chennai Python Meetup November 2026"
    assert c.url == "https://example.com/events/chennai-python-nov-2026"
    assert "FastAPI" in (c.description or "")
    assert c.organizer == "ChennaiPy Community"
    assert "python" in c.tags


@pytest.mark.anyio
async def test_jsonld_connector():
    jsonld_html = """<!DOCTYPE html>
    <html>
    <head>
        <script type="application/ld+json">
        {
            "@context": "https://schema.org",
            "@type": "Event",
            "name": "Coimbatore Web3 & Open Source Summit",
            "startDate": "2026-12-05T09:30:00+05:30",
            "endDate": "2026-12-06T18:00:00+05:30",
            "eventAttendanceMode": "https://schema.org/OfflineEventAttendanceMode",
            "description": "Two days of developer workshops, hackathons, and keynotes in Coimbatore.",
            "location": {
                "@type": "Place",
                "name": "Codissia Trade Fair Complex",
                "address": {
                    "@type": "PostalAddress",
                    "addressLocality": "Coimbatore",
                    "addressRegion": "Tamil Nadu"
                }
            },
            "organizer": {
                "@type": "Organization",
                "name": "Kovai FOSS Collective",
                "url": "https://example.com/kovai-foss"
            },
            "offers": {
                "@type": "Offer",
                "price": "0",
                "priceCurrency": "INR",
                "url": "https://example.com/register/coimbatore"
            }
        }
        </script>
    </head>
    <body><h1>Events</h1></body>
    </html>"""

    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.text = jsonld_html

    mock_fetcher = AsyncMock()
    mock_fetcher.fetch.return_value = mock_resp

    source = DiscoverySource(
        id=2,
        name="Test JSON-LD",
        base_url="https://example.com/summit",
        source_type="jsonld",
    )

    connector = JsonLdConnector()
    candidates = await connector.extract_candidates(source, mock_fetcher)

    assert len(candidates) == 1
    c = candidates[0]
    assert c.title == "Coimbatore Web3 & Open Source Summit"
    assert c.venue == "Codissia Trade Fair Complex"
    assert c.city == "Coimbatore"
    assert c.organizer == "Kovai FOSS Collective"
    assert c.participation_fee == 0.0
    assert c.registration_url == "https://example.com/register/coimbatore"


@pytest.mark.anyio
async def test_html_connector():
    html_page = """<html><body>
        <div class="event-card">
            <h3 class="title">Madurai Heritage Hackathon 2026</h3>
            <span class="event-date">2026-12-10 10:00</span>
            <p class="desc">Build digital archives and mobile apps celebrating Tamil literature and temple architecture.</p>
            <span class="organizer">Madurai Techies</span>
            <a href="/hackathons/madurai-2026">Register Now</a>
        </div>
    </body></html>"""

    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.text = html_page

    mock_fetcher = AsyncMock()
    mock_fetcher.fetch.return_value = mock_resp

    source = DiscoverySource(
        id=3,
        name="Test HTML",
        base_url="https://example.com/events",
        source_type="html",
    )

    connector = HTMLConnector()
    candidates = await connector.extract_candidates(source, mock_fetcher)

    assert len(candidates) == 1
    c = candidates[0]
    assert c.title == "Madurai Heritage Hackathon 2026"
    assert c.url == "https://example.com/hackathons/madurai-2026"
    assert "Tamil literature" in (c.description or "")
    assert c.organizer == "Madurai Techies"


@pytest.mark.anyio
async def test_api_connector():
    api_json = {
        "events": [
            {
                "id": "tn-fest-101",
                "title": "Trichy Robotics & IoT Symposium",
                "date": "2026-11-28T09:00:00Z",
                "url": "https://example.com/symposium/trichy",
                "organizer": "NIT Trichy Robotics Club",
                "description": "Student paper presentations and autonomous bot competitions.",
                "city": "Tiruchirappalli",
                "price": 150
            }
        ]
    }

    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.json.return_value = api_json

    mock_fetcher = AsyncMock()
    mock_fetcher.fetch.return_value = mock_resp

    source = DiscoverySource(
        id=4,
        name="Test API",
        base_url="https://api.example.com/events",
        source_type="api",
    )

    connector = APIConnector()
    candidates = await connector.extract_candidates(source, mock_fetcher)

    assert len(candidates) == 1
    c = candidates[0]
    assert c.title == "Trichy Robotics & IoT Symposium"
    assert c.organizer == "NIT Trichy Robotics Club"
    assert c.city == "Tiruchirappalli"
    assert c.participation_fee == 150.0
    assert c.external_id == "tn-fest-101"


def test_registry_lookup():
    assert isinstance(get_connector("rss"), RSSConnector)
    assert isinstance(get_connector("jsonld"), JsonLdConnector)
    assert isinstance(get_connector("html"), HTMLConnector)
    assert isinstance(get_connector("api"), APIConnector)
    with pytest.raises(ValueError):
        get_connector("unsupported_type")

