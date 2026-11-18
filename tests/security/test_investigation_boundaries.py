from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.main import create_app
from app.models import User
from app.models.workflow import WorkflowBase
from scripts.seed_demo_data import seed_demo


@pytest.fixture
def sandbox_client(engine):
    WorkflowBase.metadata.create_all(engine)
    with Session(engine) as session, session.begin():
        seed_demo(session)
    config = Settings(_env_file=None, app_env="test", demo_mode=True, investigation_sandbox=True)
    with TestClient(create_app(config, engine)) as client:
        yield client


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"X-FraudSentinel-Sandbox": "wrong"},
        {"X-FraudSentinel-Sandbox": "synthetic-only", "Origin": "https://attacker.invalid"},
        {"X-FraudSentinel-Sandbox": "synthetic-only", "Sec-Fetch-Site": "cross-site"},
        {"X-FraudSentinel-Sandbox": "synthetic-only", "Host": "rebinding.invalid"},
    ],
)
def test_mutations_fail_before_database_for_untrusted_requests(sandbox_client, engine, headers):
    with patch.object(
        engine, "connect", side_effect=AssertionError("Database must not be reached")
    ):
        response = sandbox_client.post(
            "/api/v1/intelligence/cases",
            headers=headers,
            json={"case_id": "attempt", "title": "Denied"},
        )
    assert response.status_code == 403


def test_oversized_body_is_bounded_and_not_reflected(sandbox_client, engine):
    with patch.object(
        engine, "connect", side_effect=AssertionError("Database must not be reached")
    ):
        response = sandbox_client.post(
            "/api/v1/intelligence/cases",
            headers={
                "X-FraudSentinel-Sandbox": "synthetic-only",
                "Content-Type": "application/json",
            },
            content=b"x" * 1_048_577,
        )
    assert response.status_code == 413
    assert response.headers["cache-control"] == "no-store"


def test_revoked_role_cannot_query_intelligence(sandbox_client, engine):
    with Session(engine) as session, session.begin():
        session.get(User, "user_demo_analyst").role = "reviewer"
    assert sandbox_client.get("/api/v1/intelligence/transactions").status_code == 403


def test_active_database_cannot_be_enabled_by_sandbox_flag():
    config = Settings(_env_file=None, demo_mode=True, investigation_sandbox=True)
    database = create_engine("postgresql+psycopg://localhost/fraudsentinel")
    with patch.object(database, "connect", side_effect=AssertionError("No connection permitted")):
        with pytest.raises(ValueError, match="isolated synthetic database"):
            create_app(config, database)
    database.dispose()


def test_production_and_non_demo_modes_cannot_enable_sandbox():
    for values in (
        {"app_env": "production", "demo_mode": True},
        {"app_env": "test", "demo_mode": False},
    ):
        with pytest.raises(ValidationError):
            Settings(_env_file=None, investigation_sandbox=True, **values)


@pytest.mark.parametrize(
    "path", ["/api/v1/agents/execute", "/api/v1/approvals", "/api/v1/intelligence/tools/execute"]
)
def test_agent_and_approval_execution_remains_unavailable(sandbox_client, engine, path):
    with patch.object(engine, "connect", side_effect=AssertionError("Executor cannot be reached")):
        assert (
            sandbox_client.post(path, json={"tool": "sql", "command": "SELECT *"}).status_code
            == 404
        )
