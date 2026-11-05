import time
from app.core.config import settings
from app.core.security import create_access_token


def test_admin_login_success(client):
    res = client.post(
        "/api/v1/admin/login",
        json={"email": settings.admin_email, "password": settings.admin_password},
    )
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_admin_login_invalid_password(client):
    res = client.post(
        "/api/v1/admin/login",
        json={"email": settings.admin_email, "password": "WrongPassword123!"},
    )
    assert res.status_code == 401
    assert "Invalid email or password" in res.json()["detail"]


def test_admin_login_nonexistent_email(client):
    res = client.post(
        "/api/v1/admin/login",
        json={"email": "nonexistent@example.com", "password": "AnyPassword"},
    )
    assert res.status_code == 401


def test_missing_token_authorization(client):
    res = client.get("/api/v1/admin/metrics")
    assert res.status_code == 401


def test_invalid_token_authorization(client):
    res = client.get("/api/v1/admin/metrics", headers={"Authorization": "Bearer invalid.gibberish.token"})
    assert res.status_code == 401


def test_expired_token_authorization(client, monkeypatch):
    monkeypatch.setattr(settings, "access_token_expire_minutes", -10)
    expired_token = create_access_token(settings.admin_email)
    res = client.get("/api/v1/admin/metrics", headers={"Authorization": f"Bearer {expired_token}"})
    assert res.status_code == 401


def test_publish_and_reject_operations(client, admin_headers, sample_draft_event):
    event_id = sample_draft_event.id

    # 1. Publish
    pub_res = client.patch(f"/api/v1/admin/events/{event_id}/publish", headers=admin_headers)
    assert pub_res.status_code == 200
    assert pub_res.json()["status"] == "published"
    assert pub_res.json()["is_published"] is True

    # Check publicly visible
    pub_check = client.get(f"/api/v1/events/{sample_draft_event.slug}")
    assert pub_check.status_code == 200

    # 2. Reject
    rej_res = client.patch(f"/api/v1/admin/events/{event_id}/reject", headers=admin_headers)
    assert rej_res.status_code == 200
    assert rej_res.json()["status"] == "rejected"
    assert rej_res.json()["is_published"] is False

    # Check no longer publicly visible
    hidden_check = client.get(f"/api/v1/events/{sample_draft_event.slug}")
    assert hidden_check.status_code == 404


def test_feature_and_unfeature_toggle(client, admin_headers, sample_published_event):
    event_id = sample_published_event.id
    assert sample_published_event.is_featured is True

    # 1. Unfeature
    unfeat_res = client.patch(f"/api/v1/admin/events/{event_id}/unfeature", headers=admin_headers)
    assert unfeat_res.status_code == 200
    assert unfeat_res.json()["is_featured"] is False

    # 2. Toggle via feature endpoint
    feat_res = client.patch(f"/api/v1/admin/events/{event_id}/feature", headers=admin_headers)
    assert feat_res.status_code == 200
    assert feat_res.json()["is_featured"] is True


def test_admin_metrics_endpoint(client, admin_headers, sample_published_event, sample_draft_event):
    res = client.get("/api/v1/admin/metrics", headers=admin_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["total_events"] == 2
    assert data["published_events"] == 1
    assert data["draft_events"] == 1
    assert data["featured_events"] == 1
    assert data["total_categories"] >= 1
    assert data["total_locations"] >= 1


def test_admin_category_management(client, admin_headers):
    # 1. Create
    cat_payload = {
        "name": "Design & UI/UX",
        "description": "Design thinking and interface engineering meetups.",
    }
    create_res = client.post("/api/v1/admin/categories", json=cat_payload, headers=admin_headers)
    assert create_res.status_code == 201
    cat_id = create_res.json()["id"]
    assert create_res.json()["slug"] == "design-ui-ux"

    # 2. Edit
    edit_payload = {"name": "Design & Creative Tech"}
    edit_res = client.put(f"/api/v1/admin/categories/{cat_id}", json=edit_payload, headers=admin_headers)
    assert edit_res.status_code == 200
    assert edit_res.json()["name"] == "Design & Creative Tech"

    # 3. Deactivate
    deact_res = client.patch(f"/api/v1/admin/categories/{cat_id}/deactivate", headers=admin_headers)
    assert deact_res.status_code == 200
    assert deact_res.json()["is_active"] is False

    # 4. Delete
    del_res = client.delete(f"/api/v1/admin/categories/{cat_id}", headers=admin_headers)
    assert del_res.status_code == 204


def test_admin_location_management(client, admin_headers):
    # 1. Create
    loc_payload = {
        "name": "Tidel Park Auditorium",
        "city": "Chennai",
        "district": "Chennai",
        "state": "Tamil Nadu",
        "address": "Rajiv Gandhi Salai, Taramani",
    }
    create_res = client.post("/api/v1/admin/locations", json=loc_payload, headers=admin_headers)
    assert create_res.status_code == 201
    loc_id = create_res.json()["id"]

    # 2. Edit
    edit_res = client.put(
        f"/api/v1/admin/locations/{loc_id}",
        json={"address": "Updated Address Taramani"},
        headers=admin_headers,
    )
    assert edit_res.status_code == 200
    assert edit_res.json()["address"] == "Updated Address Taramani"

    # 3. Delete
    del_res = client.delete(f"/api/v1/admin/locations/{loc_id}", headers=admin_headers)
    assert del_res.status_code == 204

