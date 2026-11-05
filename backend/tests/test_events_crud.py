from datetime import datetime, timedelta, timezone


def test_create_event_success(client, admin_headers, sample_category, sample_location):
    now = datetime.now(timezone.utc)
    payload = {
        "title": "Coimbatore AI Hackathon 2026",
        "short_description": "Premier hackathon in Coimbatore",
        "description": "Comprehensive hackathon for collegiate and professional developers.",
        "organizer_name": "Coimbatore Coding Club",
        "organizer_website": "https://example.com/cbe",
        "registration_url": "https://example.com/register",
        "official_website": "https://example.com/official",
        "banner_url": "https://example.com/banner.png",
        "contact_email": "hack@example.com",
        "event_type": "hackathon",
        "mode": "hybrid",
        "start_date": (now + timedelta(days=20)).isoformat(),
        "end_date": (now + timedelta(days=22)).isoformat(),
        "registration_deadline": (now + timedelta(days=15)).isoformat(),
        "state": "Tamil Nadu",
        "district": "Coimbatore",
        "city": "Coimbatore",
        "venue": "CODISSIA Trade Fair Complex",
        "eligibility": "College students and working professionals",
        "participation_fee": 250.0,
        "currency": "INR",
        "tags": ["AI", "Hackathon", "Coimbatore"],
        "status": "published",
        "is_published": True,
        "is_featured": True,
        "category_id": sample_category.id,
        "location_id": sample_location.id,
    }

    response = client.post("/api/v1/admin/events", json=payload, headers=admin_headers)
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == payload["title"]
    assert data["slug"] == "coimbatore-ai-hackathon-2026"
    assert data["participation_fee"] == 250.0
    assert data["currency"] == "INR"
    assert data["tags"] == ["AI", "Hackathon", "Coimbatore"]
    assert data["status"] == "published"
    assert data["is_published"] is True
    assert data["is_featured"] is True
    assert data["id"] is not None


def test_edit_event_success(client, admin_headers, sample_published_event):
    event_id = sample_published_event.id
    update_payload = {
        "title": "Chennai Tech Expo 2026 - Revised",
        "participation_fee": 750.0,
        "venue": "ITC Grand Chola",
    }

    response = client.put(f"/api/v1/admin/events/{event_id}", json=update_payload, headers=admin_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Chennai Tech Expo 2026 - Revised"
    assert data["participation_fee"] == 750.0
    assert data["venue"] == "ITC Grand Chola"


def test_delete_event_success(client, admin_headers, sample_published_event):
    event_id = sample_published_event.id

    response = client.delete(f"/api/v1/admin/events/{event_id}", headers=admin_headers)
    assert response.status_code == 204

    # Verify event no longer accessible publicly or in admin
    get_res = client.get(f"/api/v1/events/{sample_published_event.slug}")
    assert get_res.status_code == 404

    admin_get = client.get(f"/api/v1/admin/events/{event_id}", headers=admin_headers)
    assert admin_get.status_code == 404


def test_duplicate_slug_explicit_conflict(client, admin_headers, sample_published_event):
    now = datetime.now(timezone.utc)
    payload = {
        "title": "Different Event With Same Slug",
        "slug": sample_published_event.slug,
        "description": "Event attempting duplicate slug collision.",
        "organizer_name": "Rogue Organizer",
        "registration_url": "https://example.com/reg",
        "start_date": (now + timedelta(days=30)).isoformat(),
    }

    response = client.post("/api/v1/admin/events", json=payload, headers=admin_headers)
    assert response.status_code == 409
    assert "already exists" in response.json()["detail"]


def test_duplicate_slug_auto_generated(client, admin_headers):
    now = datetime.now(timezone.utc)
    base_payload = {
        "title": "Madurai Developer Meetup",
        "description": "Monthly developer meetup in Madurai.",
        "organizer_name": "Madurai Devs",
        "registration_url": "https://example.com/meetup",
        "start_date": (now + timedelta(days=10)).isoformat(),
    }

    res1 = client.post("/api/v1/admin/events", json=base_payload, headers=admin_headers)
    assert res1.status_code == 201
    assert res1.json()["slug"] == "madurai-developer-meetup"

    res2 = client.post("/api/v1/admin/events", json=base_payload, headers=admin_headers)
    assert res2.status_code == 201
    assert res2.json()["slug"] == "madurai-developer-meetup-2"


def test_invalid_registration_url(client, admin_headers):
    now = datetime.now(timezone.utc)
    payload = {
        "title": "Invalid URL Event",
        "description": "Testing invalid registration URL validation.",
        "organizer_name": "Organizer",
        "registration_url": "ftp://not-an-http-url.com",
        "start_date": (now + timedelta(days=10)).isoformat(),
    }

    response = client.post("/api/v1/admin/events", json=payload, headers=admin_headers)
    assert response.status_code == 422


def test_invalid_date_range(client, admin_headers):
    now = datetime.now(timezone.utc)
    payload = {
        "title": "Invalid Date Range Event",
        "description": "End date earlier than start date.",
        "organizer_name": "Organizer",
        "registration_url": "https://example.com/reg",
        "start_date": (now + timedelta(days=10)).isoformat(),
        "end_date": (now + timedelta(days=5)).isoformat(),  # 5 days earlier!
    }

    response = client.post("/api/v1/admin/events", json=payload, headers=admin_headers)
    assert response.status_code == 422


def test_invalid_participation_fee(client, admin_headers):
    now = datetime.now(timezone.utc)
    payload = {
        "title": "Negative Fee Event",
        "description": "Participation fee cannot be negative.",
        "organizer_name": "Organizer",
        "registration_url": "https://example.com/reg",
        "start_date": (now + timedelta(days=10)).isoformat(),
        "participation_fee": -100.0,
    }

    response = client.post("/api/v1/admin/events", json=payload, headers=admin_headers)
    assert response.status_code == 422

