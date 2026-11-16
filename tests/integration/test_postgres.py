"""Opt-in checks against PostgreSQL, isolated in a transaction-scoped test schema."""

import os
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import func, inspect, select, text
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateSchema

from app.core.config import Settings
from app.db.session import create_db_engine
from app.models import Transaction
from scripts.seed_demo_data import seed_demo

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_POSTGRES_TESTS") != "1",
    reason="Set RUN_POSTGRES_TESTS=1 with a local PostgreSQL database to run migration checks",
)


def test_postgres_migration_round_trip_and_seed():
    engine = create_db_engine(Settings())
    try:
        with engine.connect() as connection:
            outer = connection.begin()
            try:
                schema = f"test_{uuid4().hex}"
                connection.execute(CreateSchema(schema))
                connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))
                config = Config(str(Path(__file__).resolve().parents[2] / "backend/alembic.ini"))
                config.attributes["connection"] = connection
                command.upgrade(config, "head")
                assert len(inspect(connection).get_table_names()) == 9
                with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
                    with session.begin():
                        seed_demo(session)
                        seed_demo(session)
                    assert session.scalar(select(func.count()).select_from(Transaction)) == 6
                    transaction = session.get(Transaction, "txn_demo_006")
                    assert transaction.occurred_at.astimezone(UTC) == datetime(
                        2026, 11, 15, 20, 44, tzinfo=UTC
                    )
                command.check(config)
                command.downgrade(config, "base")
                assert "transactions" not in inspect(connection).get_table_names()
                command.upgrade(config, "head")
                assert "transactions" in inspect(connection).get_table_names()
            finally:
                outer.rollback()  # Discards the test schema and all test data.
    finally:
        engine.dispose()
