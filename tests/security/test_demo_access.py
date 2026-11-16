import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.config import Settings
from app.main import create_app


def test_demo_disabled_by_default(engine, monkeypatch):
    monkeypatch.delenv("DEMO_MODE", raising=False)
    config = Settings(_env_file=None)
    with TestClient(create_app(config, engine)) as client:
        assert client.get("/api/v1/demo/overview").status_code == 403


def test_production_rejects_demo_identity():
    with pytest.raises(ValidationError, match="DEMO_MODE must be disabled"):
        Settings(_env_file=None, app_env="production", demo_mode=True)


def test_production_requires_database_password():
    with pytest.raises(ValidationError, match="POSTGRES_PASSWORD is required"):
        Settings(_env_file=None, app_env="production", demo_mode=False, postgres_password="")


def test_production_disables_openapi(engine):
    config = Settings(
        _env_file=None,
        app_env="production",
        demo_mode=False,
        postgres_password="test-placeholder-not-a-real-password",
    )
    with TestClient(create_app(config, engine)) as client:
        assert client.get("/docs").status_code == 404
        assert client.get("/openapi.json").status_code == 404
        assert client.get("/api/v1/demo/overview").status_code == 403
