from unittest.mock import patch

import pytest
from sqlalchemy import event
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.models import User
from scripts.seed_demo_data import seed_demo


def test_revoked_demo_role_cannot_read_case_records(client, engine):
    with Session(engine) as session, session.begin():
        seed_demo(session)
        session.get(User, "user_demo_analyst").role = "viewer"
    statements = []

    def record_statement(connection, cursor, statement, parameters, context, executemany):
        statements.append(statement.lower())

    event.listen(engine, "before_cursor_execute", record_statement)
    try:
        response = client.get("/api/v1/demo/overview")
    finally:
        event.remove(engine, "before_cursor_execute", record_statement)
    assert response.status_code == 403
    assert not any("from transactions" in query or "from cases" in query for query in statements)


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/agent/requests",
        "/api/v1/cases/case_demo_001/investigate",
        "/api/v1/approvals",
    ],
)
def test_unimplemented_sensitive_operations_cannot_reach_database(client, engine, path):
    with patch.object(engine, "connect", side_effect=AssertionError("Executor must not run")):
        response = client.post(path, json={"tool": "arbitrary_sql", "query": "SELECT * FROM users"})
    assert response.status_code == 404


def test_cors_preflight_permits_only_existing_get_operations(client):
    headers = {
        "Origin": "http://localhost:5173",
        "Access-Control-Request-Method": "GET",
        "Access-Control-Request-Headers": "Content-Type",
    }
    allowed = client.options("/api/v1/demo/overview", headers=headers)
    denied = client.options(
        "/api/v1/demo/overview",
        headers={**headers, "Access-Control-Request-Method": "POST"},
    )
    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-methods"] == "GET"
    assert "access-control-allow-credentials" not in allowed.headers
    assert denied.status_code == 400


def test_database_failure_response_hides_sql_and_parameters(client, engine):
    secret = "FAKE_PRIVATE_DATABASE_VALUE"
    error = OperationalError(
        "SELECT secret_column FROM users", {"password": secret}, Exception(secret)
    )
    with patch.object(engine, "connect", side_effect=error):
        response = client.get("/api/v1/demo/overview")
    assert response.status_code == 503
    assert response.json() == {"detail": "Database unavailable"}
    assert secret not in response.text
    assert "secret_column" not in response.text
