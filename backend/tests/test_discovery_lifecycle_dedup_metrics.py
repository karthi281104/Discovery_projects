from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.discovery.deduplicator import (
    compute_event_content_hash,
    find_matching_event,
    normalize_title_for_comparison,
)
from app.discovery.lifecycle import handle_duplicate_event_update
from app.models import (
    DiscoveredUrl,
    DiscoveryRun,
    DiscoverySource,
    Event,
    SearchCampaign,
    SearchQueryExecution,
)


def test_compute_event_content_hash_deterministic():
    dt = datetime(2026, 11, 20, 10, 0, tzinfo=timezone.utc)
    hash1 = compute_event_content_hash("Chennai AI & Cloud Summit 2026!", dt, "Chennai")
    hash2 = compute_event_content_hash("  chennai ai cloud summit 2026   ", dt, " chennai ")
    
    assert len(hash1) == 64
    assert hash1 == hash2


def test_deduplicator_primary_key_content_hash(db: Session):
    now = datetime(2026, 11, 20, 9, 0, tzinfo=timezone.utc)
    ev_hash = compute_event_content_hash("Madurai Hackathon 2026", now, "Madurai")

    event = Event(
        title="Madurai Hackathon 2026",
        slug="madurai-hackathon-2026",
        description="A major regional hackathon",
        organizer_name="Madurai Tech Hub",
        registration_url="https://example.com/madurai-hack",
        start_date=now,
        city="Madurai",
        state="Tamil Nadu",
        content_hash=ev_hash,
        status="published",
        is_published=True,
    )
    db.add(event)
    db.commit()

    # Query with exact normalized attributes -> matches by content_hash primary key
    match = find_matching_event(
        db,
        title="Madurai Hackathon 2026",
        start_date=now,
        city="Madurai",
    )
    assert match is not None
    assert match.id == event.id


def test_deduplicator_fuzzy_cross_source_check(db: Session):
    now = datetime(2026, 11, 20, 9, 0, tzinfo=timezone.utc)
    event = Event(
        title="Kovai AI Hackathon 2026",
        slug="kovai-ai-hackathon-2026",
        description="Tech symposium and hackathon in Coimbatore",
        organizer_name="PSG Tech",
        registration_url="https://psg.edu/hackathon",
        start_date=now,
        city="Coimbatore",
        state="Tamil Nadu",
        content_hash="some-hash",
        status="published",
        is_published=True,
    )
    db.add(event)
    db.commit()

    # Candidate has slightly rearranged title ("Kovai 2026 AI Hackathon") and is 1 day later (within +/- 2 days)
    candidate_date = now + timedelta(days=1)
    match = find_matching_event(
        db,
        title="Kovai 2026 AI Hackathon",
        start_date=candidate_date,
        city="Coimbatore",
    )
    assert match is not None
    assert match.id == event.id

    # Candidate with date 5 days away (+/- 2 day window exceeded) -> should NOT match
    far_date = now + timedelta(days=5)
    match_far = find_matching_event(
        db,
        title="Kovai 2026 AI Hackathon",
        start_date=far_date,
        city="Coimbatore",
    )
    assert match_far is None

    # Candidate in different city (Salem vs Coimbatore) -> should NOT match
    match_diff_city = find_matching_event(
        db,
        title="Kovai 2026 AI Hackathon",
        start_date=candidate_date,
        city="Salem",
    )
    assert match_diff_city is None


def test_handle_duplicate_event_update(db: Session):
    now = datetime(2026, 11, 20, 9, 0, tzinfo=timezone.utc)
    event = Event(
        title="Trichy Cyber Security Summit 2026",
        slug="trichy-cyber-security-summit-2026",
        description="Cyber security conference in Trichy",
        organizer_name="NIT Trichy",
        registration_url="https://nitt.edu/summit",
        original_source_url="https://nitt.edu/event-original",
        additional_source_urls=[],
        start_date=now,
        venue="NIT Campus Hall 1",
        city="Tiruchirappalli",
        state="Tamil Nadu",
        content_hash="trichy-hash-1",
        update_history=[],
        status="published",
        is_published=True,
    )
    db.add(event)
    db.commit()

    new_source = "https://knowafest.com/trichy-summit"
    new_start = now + timedelta(days=1)
    new_venue = "NIT Campus Auditorium B"
    new_reg = "https://nitt.edu/summit/register-now"

    # 1. First update with field changes
    updated = handle_duplicate_event_update(
        db,
        event,
        new_source_url=new_source,
        new_start_date=new_start,
        new_venue_name=new_venue,
        new_registration_url=new_reg,
        as_of=now,
    )
    assert updated is True
    assert event.additional_source_urls == [new_source]
    assert event.venue == new_venue
    assert event.registration_url == new_reg
    assert event.start_date == new_start
    assert len(event.update_history) == 1

    diff = event.update_history[0]
    assert diff["source_url"] == new_source
    assert "start_date" in diff["changes"]
    assert "venue_name" in diff["changes"]
    assert "registration_url" in diff["changes"]
    assert diff["changes"]["venue_name"]["old"] == "NIT Campus Hall 1"
    assert diff["changes"]["venue_name"]["new"] == "NIT Campus Auditorium B"

    # 2. Subsequent call with identical fields -> No changes, returns False
    updated_again = handle_duplicate_event_update(
        db,
        event,
        new_source_url=new_source,
        new_start_date=new_start,
        new_venue_name=new_venue,
        new_registration_url=new_reg,
        as_of=now,
    )
    assert updated_again is False
    # URL list is not duplicated
    assert event.additional_source_urls == [new_source]
    assert len(event.update_history) == 1


def test_get_discovery_metrics_exact_14_counts(client, admin_headers, db: Session):
    now = datetime(2026, 11, 20, 10, 0, tzinfo=timezone.utc)

    # Seed data across discovery tables
    source = DiscoverySource(
        name="Test Telemetry Source",
        base_url="https://example.com/rss.xml",
        source_type="rss",
        region="Tamil Nadu",
        is_enabled=True,
        crawl_interval=60,
    )
    db.add(source)
    db.flush()

    run = DiscoveryRun(
        source_id=source.id,
        started_at=now,
        completed_at=now + timedelta(seconds=12),
        status="success",
        pages_checked=5,
        candidates_found=8,
        events_created=4,
        events_updated=2,
        duplicates_skipped=2,
        validation_failures=1,
    )
    db.add(run)

    event1 = Event(
        title="Published Telemetry Event",
        slug="published-telemetry-event",
        description="Event description",
        organizer_name="Org 1",
        registration_url="https://example.com/pub1",
        start_date=now + timedelta(days=10),
        status="published",
        is_published=True,
        validation_outcome="auto_published",
        confidence_score=0.92,
        original_source_url="https://example.com/source1",
    )
    event2 = Event(
        title="Review Queue Telemetry Event",
        slug="review-queue-telemetry-event",
        description="Event description",
        organizer_name="Org 2",
        registration_url="https://example.com/rev2",
        start_date=now + timedelta(days=12),
        status="pending",
        is_published=False,
        validation_outcome="needs_review",
        confidence_score=0.68,
        original_source_url="https://example.com/source2",
    )
    db.add_all([event1, event2])
    db.commit()

    resp = client.get("/api/admin/discovery/metrics", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()

    # Exact 14 telemetry counts must all exist in the response
    exact_14_fields = [
        "queries_executed",
        "search_results_collected",
        "new_urls_discovered",
        "new_sources_identified",
        "pages_successfully_fetched",
        "pages_blocked_or_inaccessible",
        "event_candidates_extracted",
        "valid_events",
        "events_published",
        "candidates_requiring_review",
        "duplicates_detected",
        "events_updated",
        "source_failures",
        "discovery_execution_duration",
    ]
    for field in exact_14_fields:
        assert field in data, f"Missing required telemetry counter: {field}"

    assert data["event_candidates_extracted"] == 8
    assert data["events_published"] >= 1
    assert data["candidates_requiring_review"] >= 1
    assert data["duplicates_detected"] == 2
    assert data["events_updated"] == 2
    assert data["discovery_execution_duration"] >= 12.0


def test_discovery_review_queue_and_published_events_endpoints(client, admin_headers, db: Session):
    now = datetime(2026, 11, 20, 10, 0, tzinfo=timezone.utc)

    event_rev = Event(
        title="Review Queue Candidate Event",
        slug="review-queue-candidate-event",
        description="Needs review due to medium confidence",
        organizer_name="Campus Club",
        registration_url="https://example.com/review-reg",
        start_date=now + timedelta(days=5),
        status="pending",
        is_published=False,
        validation_outcome="needs_review",
        confidence_score=0.72,
        original_source_url="https://example.com/original-review-url",
        additional_source_urls=["https://secondary.com/review-url"],
        update_history=[
            {
                "timestamp": now.isoformat(),
                "source_url": "https://secondary.com/review-url",
                "changes": {
                    "venue_name": {"old": "Old Hall", "new": "New Auditorium"}
                },
            }
        ],
    )
    db.add(event_rev)
    db.commit()

    # 1. Test GET /api/admin/discovery/review-queue
    resp_rq = client.get("/api/admin/discovery/review-queue", headers=admin_headers)
    assert resp_rq.status_code == 200
    rq_items = resp_rq.json()
    assert len(rq_items) >= 1
    rq_event = next(e for e in rq_items if e["id"] == event_rev.id)
    assert rq_event["title"] == "Review Queue Candidate Event"
    assert rq_event["original_source_url"] == "https://example.com/original-review-url"
    assert rq_event["additional_source_urls"] == ["https://secondary.com/review-url"]
    assert len(rq_event["update_history"]) == 1

    # 2. Test GET /api/admin/discovery/published-events
    resp_pub = client.get("/api/admin/discovery/published-events", headers=admin_headers)
    assert resp_pub.status_code == 200
    pub_items = resp_pub.json()
    assert isinstance(pub_items, list)

