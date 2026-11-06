from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from app.discovery.normalizer import (
    clean_text,
    detect_district_and_city,
    detect_event_type,
    normalize_url,
    parse_and_localize_date,
)
from app.discovery.validator import validate_candidate


def test_clean_text():
    html_input = "<p>Join us for the <b>Tamil Nadu</b> Hackathon! &amp; win &#8377;50,000.</p>"
    cleaned = clean_text(html_input)
    assert cleaned == "Join us for the Tamil Nadu Hackathon! & win ₹50,000."


def test_normalize_url():
    raw_url = "https://EXAMPLE.com/events/2026/hackathon/?utm_source=facebook&utm_medium=cpc&ref=xyz#register"
    canonical = normalize_url(raw_url)
    assert canonical == "https://example.com/events/2026/hackathon"


def test_parse_and_localize_date():
    # Naive date string
    naive_str = "2026-11-20 09:30:00"
    dt = parse_and_localize_date(naive_str)
    assert dt is not None
    assert dt.tzinfo == timezone.utc
    # 09:30 in Asia/Kolkata (+05:30) is 04:00 UTC
    assert dt.hour == 4
    assert dt.minute == 0


def test_detect_event_type():
    assert detect_event_type("State Level Coding Contest 2026", None) == "competition"
    assert detect_event_type("Chennai AI Hackfest", None) == "hackathon"
    assert detect_event_type("International Conference on Green Tech", None) == "conference"
    assert detect_event_type("National Symposium on Embedded Systems", None) == "symposium"
    assert detect_event_type("Hands-on Flutter Bootcamp", None) == "workshop"
    assert detect_event_type("Startup Pitch Summit", None) == "startup"
    assert detect_event_type("Open Source Contribution Sprint", None) == "open_source"


def test_detect_district_and_city():
    district, city = detect_district_and_city("Madurai Kamaraj University, Madurai", None, "Tamil Nadu")
    assert district == "Madurai"
    assert city == "Madurai"

    district2, city2 = detect_district_and_city("Codissia Complex, Coimbatore", "Coimbatore", "")
    assert district2 == "Coimbatore"
    assert city2 == "Coimbatore"


def test_validate_candidate_valid():
    start_date = datetime(2026, 12, 1, 10, 0, tzinfo=timezone.utc)
    result = validate_candidate(
        title="Tamil Nadu AI & Cloud Summit 2026",
        description="A premier 2-day conference bringing together cloud architects, AI researchers, and developers in Chennai.",
        start_date=start_date,
        end_date=datetime(2026, 12, 2, 18, 0, tzinfo=timezone.utc),
        registration_url="https://example.com/register",
        organizer_name="Tamil Nadu Cloud Developers",
        venue="Chennai Trade Centre",
        city="Chennai",
    )
    assert result.is_valid is True
    assert result.confidence_score >= 0.70
    assert len(result.rejection_reasons) == 0


def test_validate_candidate_rejects_generic_title():
    start_date = datetime(2026, 12, 1, 10, 0, tzinfo=timezone.utc)
    result = validate_candidate(
        title="Upcoming Events",
        description="Detailed description of events happening this month.",
        start_date=start_date,
        end_date=None,
        registration_url="https://example.com/events",
        organizer_name="Organizer",
    )
    assert result.is_valid is False
    assert any("generic" in r for r in result.rejection_reasons)


def test_validate_candidate_rejects_missing_date():
    result = validate_candidate(
        title="Tamil Nadu Developer Summit",
        description="Valid description with enough characters to pass length check.",
        start_date=None,
        end_date=None,
        registration_url="https://example.com/register",
        organizer_name="Organizer",
    )
    assert result.is_valid is False
    assert any("Start date is missing" in r for r in result.rejection_reasons)
