from fastapi.testclient import TestClient

from app.main import app
from app.api import health

client = TestClient(app)


def test_health_returns_ok_when_database_is_available(monkeypatch):
    monkeypatch.setattr(health, "check_database_connection", lambda: True)

    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["database"] == "connected"


def test_health_returns_503_when_database_is_unavailable(monkeypatch):
    def fail_connection():
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(health, "check_database_connection", fail_connection)

    response = client.get("/api/v1/health")

    assert response.status_code == 503
    assert response.json()["detail"]["status"] == "unhealthy"
