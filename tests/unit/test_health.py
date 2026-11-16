from unittest.mock import patch

from sqlalchemy.exc import OperationalError

from app.db.base import Base


def test_liveness_does_not_require_database(client, engine):
    with patch.object(engine, "connect", side_effect=AssertionError("No database access allowed")):
        for path in ("/health", "/api/v1/health"):
            response = client.get(path)
            assert response.status_code == 200
            assert response.json()["status"] == "ok"
            assert response.json()["service"] == "fraudsentinel-api"


def test_readiness_checks_database_and_schema(client):
    response = client.get("/api/v1/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready", "database": "connected", "schema_ready": True}


def test_missing_schema_is_not_ready(client, engine):
    Base.metadata.drop_all(engine)
    response = client.get("/api/v1/health/ready")
    assert response.status_code == 503
    assert response.json()["database"] == "connected"
    assert response.json()["schema_ready"] is False


def test_database_outage_does_not_leak_connection_details(client, engine):
    error = OperationalError("SELECT 1", {}, Exception("private-password-do-not-expose"))
    with patch.object(engine, "connect", side_effect=error):
        response = client.get("/api/v1/health/ready")
    assert response.status_code == 503
    assert response.json()["database"] == "unavailable"
    assert "private-password" not in response.text


def test_cors_allows_only_configured_origins(client):
    allowed = client.get("/health", headers={"Origin": "http://localhost:5173"})
    denied = client.get("/health", headers={"Origin": "https://unrelated.example"})
    assert allowed.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert "access-control-allow-origin" not in denied.headers


def test_openapi_documents_health_and_demo(client):
    paths = client.get("/openapi.json").json()["paths"]
    assert "/api/v1/health/ready" in paths
    assert "/api/v1/demo/overview" in paths
