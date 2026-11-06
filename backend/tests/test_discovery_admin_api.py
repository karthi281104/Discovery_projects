from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.db.session import engine
from app.main import app
from app.models import AdminUser, DiscoveryRun, DiscoverySource


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def admin_headers():
    token = create_access_token("admin@example.com")
    return {"Authorization": f"Bearer {token}"}


def test_discovery_endpoints_require_auth(client):
    endpoints = [
        ("GET", "/api/v1/admin/discovery/sources"),
        ("POST", "/api/v1/admin/discovery/sources"),
        ("GET", "/api/v1/admin/discovery/runs"),
        ("GET", "/api/v1/admin/discovery/metrics"),
        ("POST", "/api/v1/admin/discovery/run"),
    ]
    for method, path in endpoints:
        resp = client.request(method, path)
        assert resp.status_code == 401


def test_sources_crud_and_toggle(client, admin_headers):
    # 1. Create source
    create_data = {
        "name": "Admin API Test RSS Source",
        "base_url": "https://example.com/api-test-feed.xml",
        "source_type": "rss",
        "region": "Tamil Nadu",
        "crawl_interval": 45,
    }
    create_resp = client.post("/api/v1/admin/discovery/sources", json=create_data, headers=admin_headers)
    assert create_resp.status_code == 201
    created = create_resp.json()
    source_id = created["id"]
    assert created["name"] == "Admin API Test RSS Source"
    assert created["is_enabled"] is True

    # 2. List sources
    list_resp = client.get("/api/v1/admin/discovery/sources", headers=admin_headers)
    assert list_resp.status_code == 200
    items = list_resp.json()["items"]
    assert any(s["id"] == source_id for s in items)

    # 3. Update source
    update_data = {"crawl_interval": 90, "region": "Chennai"}
    update_resp = client.put(f"/api/v1/admin/discovery/sources/{source_id}", json=update_data, headers=admin_headers)
    assert update_resp.status_code == 200
    updated = update_resp.json()
    assert updated["crawl_interval"] == 90
    assert updated["region"] == "Chennai"

    # 4. Toggle source
    toggle_resp = client.patch(f"/api/v1/admin/discovery/sources/{source_id}/toggle", headers=admin_headers)
    assert toggle_resp.status_code == 200
    assert toggle_resp.json()["is_enabled"] is False

    # Toggle back
    toggle_resp2 = client.patch(f"/api/v1/admin/discovery/sources/{source_id}/toggle", headers=admin_headers)
    assert toggle_resp2.status_code == 200
    assert toggle_resp2.json()["is_enabled"] is True

    # 5. Delete source
    del_resp = client.delete(f"/api/v1/admin/discovery/sources/{source_id}", headers=admin_headers)
    assert del_resp.status_code == 204


def test_discovery_metrics_and_runs(client, admin_headers):
    metrics_resp = client.get("/api/v1/admin/discovery/metrics", headers=admin_headers)
    assert metrics_resp.status_code == 200
    m = metrics_resp.json()
    assert "total_sources" in m
    assert "enabled_sources" in m
    assert "total_events_created" in m

    runs_resp = client.get("/api/v1/admin/discovery/runs", headers=admin_headers)
    assert runs_resp.status_code == 200
    r = runs_resp.json()
    assert "items" in r
    assert "total" in r


@patch("app.api.discovery.run_discovery_for_source")
def test_trigger_source_run(mock_run, client, admin_headers):
    with Session(engine) as session:
        src = session.scalar(select(DiscoverySource).limit(1))
        assert src is not None
        source_id = src.id

    from datetime import datetime, timezone

    mock_run.return_value = DiscoveryRun(
        id=999,
        source_id=source_id,
        started_at=datetime.now(timezone.utc),
        status="success",
        pages_checked=1,
        candidates_found=3,
        events_created=2,
        events_updated=0,
        duplicates_skipped=1,
        validation_failures=0,
    )

    resp = client.post(f"/api/v1/admin/discovery/run/{source_id}", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["events_created"] == 2
