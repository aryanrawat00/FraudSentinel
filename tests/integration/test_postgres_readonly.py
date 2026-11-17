"""Opt-in PostgreSQL checks that cannot alter existing data or run schema changes."""

import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from fastapi.testclient import TestClient
from sqlalchemy import event, inspect, text

from app.core.config import Settings
from app.db.base import Base
from app.db.session import create_db_engine
from app.main import create_app

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_POSTGRES_READONLY_TESTS") != "1",
    reason="Set RUN_POSTGRES_READONLY_TESTS=1 with an existing migrated PostgreSQL database",
)


@pytest.fixture
def readonly_engine():
    engine = create_db_engine(Settings())

    @event.listens_for(engine, "begin")
    def require_readonly(connection):
        connection.exec_driver_sql("SET TRANSACTION READ ONLY")

    yield engine
    engine.dispose()


def test_existing_postgres_schema_matches_migrations_without_writes(readonly_engine):
    config = Config(str(Path(__file__).resolve().parents[2] / "backend/alembic.ini"))
    with readonly_engine.connect() as connection, connection.begin():
        assert connection.scalar(text("SHOW transaction_read_only")) == "on"
        current = MigrationContext.configure(connection).get_current_heads()
        expected = ScriptDirectory.from_config(config).get_heads()
        assert set(current) == set(expected), "Pending migrations require separate review"
        assert set(Base.metadata.tables).issubset(inspect(connection).get_table_names())
        config.attributes["connection"] = connection
        # Since the existing revision is already head, this must be a no-op.
        # PostgreSQL's read-only transaction also prevents accidental DDL/writes.
        command.upgrade(config, "head")
        command.check(config)


def test_existing_postgres_serves_real_health_and_demo_responses(readonly_engine):
    settings = Settings()
    with TestClient(create_app(settings, readonly_engine)) as client:
        assert client.get("/health").status_code == 200
        assert client.get("/api/v1/health/ready").json() == {
            "status": "ready",
            "database": "connected",
            "schema_ready": True,
        }
        response = client.get("/api/v1/demo/overview")
        if settings.demo_mode:
            assert response.status_code == 200, "The existing demo must be seeded separately"
            assert response.json()["mode"] == "synthetic_demo"
            assert len(response.json()["recent_transactions"]) <= 6
        else:
            assert response.status_code == 403
