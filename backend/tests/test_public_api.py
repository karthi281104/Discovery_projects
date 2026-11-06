from datetime import datetime, timedelta, timezone

from app.models import Category, Event, Location


def test_published_event_visibility(client, sample_published_event):
    response = client.get("/api/v1/events")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["slug"] == sample_published_event.slug

    detail_res = client.get(f"/api/v1/events/{sample_published_event.slug}")
    assert detail_res.status_code == 200
    assert detail_res.json()["title"] == sample_published_event.title


def test_unpublished_event_invisibility(client, sample_draft_event):
    # Draft should not appear in public list
    list_res = client.get("/api/v1/events")
    assert list_res.status_code == 200
    slugs = [item["slug"] for item in list_res.json()["items"]]
    assert sample_draft_event.slug not in slugs

    # Draft should return 404 when requested by slug
    detail_res = client.get(f"/api/v1/events/{sample_draft_event.slug}")
    assert detail_res.status_code == 404


def test_search_by_title(client, sample_published_event):
    res = client.get("/api/v1/events", params={"search": "Tech Expo"})
    assert res.status_code == 200
    assert res.json()["total"] == 1

    res_none = client.get("/api/v1/events", params={"search": "NonExistentKeywordXYZ"})
    assert res_none.status_code == 200
    assert res_none.json()["total"] == 0


def test_search_by_description(client, sample_published_event):
    # Description contains "largest gathering of engineers"
    res = client.get("/api/v1/events", params={"search": "gathering of engineers"})
    assert res.status_code == 200
    assert res.json()["total"] == 1


def test_search_by_short_description(client, sample_published_event):
    # Short description contains "Annual technology summit"
    res = client.get("/api/v1/events", params={"search": "Annual technology summit"})
    assert res.status_code == 200
    assert res.json()["total"] == 1


def test_category_filtering(client, db, sample_published_event, sample_category):
    # Add a second category and event
    other_cat = Category(name="Cultural Events", slug="cultural-events", is_active=True)
    db.add(other_cat)
    db.commit()

    other_event = Event(
        title="Madurai Folk Dance Festival",
        slug="madurai-folk-dance-festival",
        description="Folk arts celebration.",
        organizer_name="Folk Arts Society",
        registration_url="https://example.com/folk",
        start_date=datetime.now(timezone.utc) + timedelta(days=15),
        status="published",
        is_published=True,
        category_id=other_cat.id,
    )
    db.add(other_event)
    db.commit()

    # Filter by category id
    res_id = client.get("/api/v1/events", params={"category_id": sample_category.id})
    assert res_id.status_code == 200
    assert res_id.json()["total"] == 1
    assert res_id.json()["items"][0]["slug"] == sample_published_event.slug

    # Filter by category slug
    res_slug = client.get("/api/v1/events", params={"category": "cultural-events"})
    assert res_slug.status_code == 200
    assert res_slug.json()["total"] == 1
    assert res_slug.json()["items"][0]["slug"] == other_event.slug


def test_city_and_district_filtering(client, db, sample_published_event):
    cbe_event = Event(
        title="Coimbatore Startup Summit",
        slug="coimbatore-startup-summit",
        description="Startup summit in Coimbatore.",
        organizer_name="Coimbatore Startups",
        registration_url="https://example.com/cbe-startup",
        start_date=datetime.now(timezone.utc) + timedelta(days=20),
        city="Coimbatore",
        district="Coimbatore",
        status="published",
        is_published=True,
    )
    db.add(cbe_event)
    db.commit()

    res_chennai = client.get("/api/v1/events", params={"city": "Chennai"})
    assert res_chennai.json()["total"] == 1
    assert res_chennai.json()["items"][0]["slug"] == sample_published_event.slug

    res_cbe = client.get("/api/v1/events", params={"district": "Coimbatore"})
    assert res_cbe.json()["total"] == 1
    assert res_cbe.json()["items"][0]["slug"] == cbe_event.slug


def test_time_filter_upcoming_excludes_cancelled_and_expired(client, db):
    now = datetime.now(timezone.utc)

    # 1. Valid upcoming published event
    ev_upcoming = Event(
        title="Upcoming Tech Conf",
        slug="upcoming-tech-conf",
        description="Valid upcoming conference.",
        organizer_name="Tech Group",
        registration_url="https://example.com/up",
        start_date=now + timedelta(days=10),
        status="published",
        is_published=True,
    )
    # 2. Cancelled event in future
    ev_cancelled = Event(
        title="Cancelled Future Summit",
        slug="cancelled-future-summit",
        description="Event that was cancelled.",
        organizer_name="Tech Group",
        registration_url="https://example.com/canc",
        start_date=now + timedelta(days=12),
        status="cancelled",
        is_published=True,
    )
    # 3. Expired event in past
    ev_expired = Event(
        title="Past Expired Meetup",
        slug="past-expired-meetup",
        description="Event that is already in past.",
        organizer_name="Tech Group",
        registration_url="https://example.com/exp",
        start_date=now - timedelta(days=10),
        end_date=now - timedelta(days=9),
        status="expired",
        is_published=True,
    )
    db.add_all([ev_upcoming, ev_cancelled, ev_expired])
    db.commit()

    res = client.get("/api/v1/events", params={"time": "upcoming"})
    assert res.status_code == 200
    slugs = [item["slug"] for item in res.json()["items"]]
    assert "upcoming-tech-conf" in slugs
    assert "cancelled-future-summit" not in slugs
    assert "past-expired-meetup" not in slugs

    # Also test GET /api/v1/events/upcoming endpoint directly
    upcoming_direct = client.get("/api/v1/events/upcoming")
    assert upcoming_direct.status_code == 200
    upcoming_slugs = [item["slug"] for item in upcoming_direct.json()]
    assert "upcoming-tech-conf" in upcoming_slugs
    assert "cancelled-future-summit" not in upcoming_slugs


def test_time_filter_uses_shared_default_duration_for_events_without_end_date(client, db):
    now = datetime.now(timezone.utc)
    short_event = Event(
        title="Short Workshop Without End",
        slug="short-workshop-without-end",
        description="A workshop with a documented default duration.",
        organizer_name="Tech Group",
        registration_url="https://example.com/short-workshop",
        start_date=now - timedelta(hours=12),
        status="published",
        is_published=True,
    )
    db.add(short_event)
    db.commit()

    active = client.get("/api/v1/events", params={"time": "active"})
    assert active.status_code == 200
    assert "short-workshop-without-end" not in {
        item["slug"] for item in active.json()["items"]
    }

    past = client.get("/api/v1/events", params={"time": "past"})
    assert past.status_code == 200
    assert "short-workshop-without-end" in {
        item["slug"] for item in past.json()["items"]
    }


def test_featured_events_endpoint(client, db, sample_published_event):
    non_featured = Event(
        title="Non-featured Standard Event",
        slug="non-featured-standard-event",
        description="Standard event description.",
        organizer_name="Tech Group",
        registration_url="https://example.com/standard",
        start_date=datetime.now(timezone.utc) + timedelta(days=5),
        status="published",
        is_published=True,
        is_featured=False,
    )
    db.add(non_featured)
    db.commit()

    res = client.get("/api/v1/events/featured")
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1
    assert data[0]["slug"] == sample_published_event.slug


def test_pagination(client, db):
    now = datetime.now(timezone.utc)
    events = [
        Event(
            title=f"Paged Event {i:02d}",
            slug=f"paged-event-{i:02d}",
            description=f"Description for paged event {i}",
            organizer_name="Organizer",
            registration_url="https://example.com/reg",
            start_date=now + timedelta(days=i + 1),
            status="published",
            is_published=True,
        )
        for i in range(15)
    ]
    db.add_all(events)
    db.commit()

    res = client.get("/api/v1/events", params={"page": 1, "page_size": 5})
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 15
    assert data["page"] == 1
    assert data["page_size"] == 5
    assert data["pages"] == 3
    assert len(data["items"]) == 5

    res_p2 = client.get("/api/v1/events", params={"page": 2, "page_size": 5})
    assert res_p2.json()["page"] == 2
    assert len(res_p2.json()["items"]) == 5


def test_categories_and_locations_listing(client, db, sample_category, sample_location):
    # Inactive category should not be returned publicly
    inactive_cat = Category(name="Old Inactive Category", slug="old-inactive", is_active=False)
    db.add(inactive_cat)
    db.commit()

    res_cat = client.get("/api/v1/categories")
    assert res_cat.status_code == 200
    slugs = [c["slug"] for c in res_cat.json()]
    assert sample_category.slug in slugs
    assert "old-inactive" not in slugs

    res_loc = client.get("/api/v1/locations")
    assert res_loc.status_code == 200
    assert len(res_loc.json()) >= 1
    assert res_loc.json()[0]["city"] == sample_location.city
