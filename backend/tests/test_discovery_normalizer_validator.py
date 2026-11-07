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
    assert result.validation_outcome == "rejected"


def test_validation_decision_thresholds():
    start_date = datetime(2026, 12, 1, 10, 0, tzinfo=timezone.utc)

    # 1. auto_published (score >= 0.80)
    res_high = validate_candidate(
        title="Anna University AI Symposium 2026",
        description="A comprehensive symposium featuring workshops, technical papers, and developer talks hosted at the campus." * 2,
        start_date=start_date,
        end_date=datetime(2026, 12, 2, 18, 0, tzinfo=timezone.utc),
        registration_url="https://annauniv.edu/events/register",
        organizer_name="Anna University College of Engineering",
        venue="Guindy Campus",
        city="Chennai",
    )
    assert res_high.validation_outcome == "auto_published"
    assert res_high.confidence_score >= 0.80
    assert res_high.is_valid is True

    # 2. needs_review (0.45 <= score < 0.80)
    # Missing accredited organizer and missing specific TN location
    res_med = validate_candidate(
        title="General Web Development Discussion",
        description="Informal meetup discussing web frameworks and modern coding practices with participants.",
        start_date=start_date,
        registration_url="https://example.com/register",
        organizer_name="Independent Group",
        venue=None,
        city=None,
        mode="offline",
    )
    assert res_med.validation_outcome == "needs_review"
    assert 0.45 <= res_med.confidence_score < 0.80
    assert res_med.is_valid is False

    # 3. rejected (< 0.45 or historical)
    res_low = validate_candidate(
        title="Old Event That Ended",
        description="Short description",
        start_date=datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc),
        end_date=datetime(2025, 1, 2, 18, 0, tzinfo=timezone.utc),
        registration_url="invalid_url",
        as_of=datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc),
    )
    assert res_low.validation_outcome == "rejected"
    assert res_low.is_valid is False

