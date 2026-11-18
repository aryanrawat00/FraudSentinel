"""Upgrade-only checks in a random PostgreSQL schema, rolled back in full.

Never changes public schema, existing application rows, or the live revision.
No downgrade is run. Credentials are loaded locally and never printed.
"""

import os
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import MetaData, inspect, select, text
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateSchema

from app.core.config import Settings
from app.db.session import create_db_engine
from app.models import RiskAssessment
from app.repositories.intelligence import IntelligenceRepository
from app.schemas.intelligence import (
    AccountCreate,
    AssessmentCreate,
    CaseCreate,
    EvidenceCreate,
    TransactionCreate,
)

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_PHASE2_POSTGRES_TESTS") != "1",
    reason="Opt in to isolated upgrade tests with RUN_PHASE2_POSTGRES_TESTS=1",
)


def test_upgrade_preserves_phase1_records_and_supports_phase2_persistence():
    settings = Settings(_env_file=os.getenv("PHASE2_TEST_ENV_FILE", ".env"))
    engine = create_db_engine(settings)
    config = Config(str(Path(__file__).resolve().parents[2] / "backend/alembic.ini"))
    schema = f"phase2_test_{uuid4().hex}"
    try:
        with engine.connect() as connection:
            outer = connection.begin()
            try:
                connection.execute(CreateSchema(schema))
                connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))
                assert connection.scalar(text("SELECT current_schema()")) == schema
                config.attributes["connection"] = connection
                command.upgrade(config, "0001_foundation")
                old = MetaData()
                old.reflect(connection)
                now = datetime(2026, 11, 17, tzinfo=UTC)
                connection.execute(
                    old.tables["users"].insert(),
                    dict(
                        user_id="fixture_user",
                        display_name="Synthetic fixture",
                        role="investigator",
                        created_at=now,
                    ),
                )
                connection.execute(
                    old.tables["cases"].insert(),
                    dict(
                        case_id="fixture_case",
                        title="Existing fixture",
                        owner_id="fixture_user",
                        status="open",
                        created_at=now,
                    ),
                )
                connection.execute(
                    old.tables["transactions"].insert(),
                    dict(
                        transaction_id="fixture_transaction",
                        case_id="fixture_case",
                        customer_id="fixture_customer",
                        amount=Decimal("12.34"),
                        currency="EUR",
                        occurred_at=now,
                        device_id="fixture_device",
                        beneficiary_id="fixture_recipient",
                    ),
                )
                connection.execute(
                    old.tables["risk_assessments"].insert(),
                    dict(
                        assessment_id="fixture_assessment",
                        transaction_id="fixture_transaction",
                        risk_score=Decimal("0.4200"),
                        reason_codes=["HISTORICAL_FIXTURE"],
                        model_version="fixture_v1",
                        created_at=now,
                    ),
                )
                connection.execute(
                    old.tables["evidence"].insert(),
                    dict(
                        evidence_id="fixture_evidence",
                        case_id="fixture_case",
                        transaction_id="fixture_transaction",
                        description="Existing synthetic evidence",
                        source="fixture_v1",
                        captured_at=now,
                    ),
                )
                before = {
                    table.name: connection.execute(select(table)).mappings().all()
                    for table in old.sorted_tables
                    if table.name != "alembic_version"
                }
                command.upgrade(config, "head")
                command.check(config)
                assert len(inspect(connection).get_table_names()) == 16
                for table in old.sorted_tables:
                    if table.name != "alembic_version":
                        assert (
                            connection.execute(select(table)).mappings().all() == before[table.name]
                        )
                migrated = connection.execute(
                    text(
                        "SELECT owner_id, source_account_id, destination_account_id, created_at "
                        "FROM transactions WHERE transaction_id = 'fixture_transaction'"
                    )
                ).one()
                assert tuple(migrated) == ("fixture_user", None, None, None)

                with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
                    with session.begin():
                        repo = IntelligenceRepository(session, "fixture_user")
                        assert repo.list_assessments("fixture_transaction")[0].score == Decimal(
                            "42"
                        )
                        for identifier in ["source", "destination"]:
                            repo.create_account(
                                AccountCreate(
                                    account_id=identifier,
                                    data_source="synthetic_test",
                                    is_synthetic=True,
                                )
                            )
                        saved = repo.create_transaction(
                            TransactionCreate(
                                transaction_id="new_tx",
                                source_account_id="source",
                                destination_account_id="destination",
                                amount="10.25",
                                currency="USD",
                                occurred_at=now,
                                transaction_type="transfer",
                                status="completed",
                                data_source="synthetic_test",
                                is_synthetic=True,
                            )
                        )
                        assert saved.case_id is None
                        repo.record_assessment(
                            AssessmentCreate(
                                assessment_id="new_assessment",
                                transaction_id="new_tx",
                                score="0",
                                risk_category="low",
                                method="rules",
                                ruleset_version="test_only",
                                status="insufficient_history",
                                factors=[],
                                missing_information=["No baseline; not evidence of fraud"],
                            )
                        )
                        repo.create_case(CaseCreate(case_id="new_case", title="Synthetic test"))
                        repo.attach_transaction("new_case", "new_tx")
                        repo.attach_account("new_case", "source")
                        saved_evidence = repo.create_evidence(
                            EvidenceCreate(
                                evidence_id="new_evidence",
                                transaction_id="new_tx",
                                case_id="new_case",
                                assessment_id="new_assessment",
                                account_id="source",
                                description="Synthetic transaction record",
                                source="fixture",
                                kind="observed_fact",
                                method="fixture_v1",
                                provenance={
                                    "source_reference": "fixture:new_tx",
                                    "source_transaction_ids": ["new_tx"],
                                    "observed_at": now,
                                },
                            )
                        )
                        assert saved_evidence.verification_status == "unverified"
                        assert session.get(
                            RiskAssessment, "fixture_assessment"
                        ).risk_score == Decimal("0.4200")
                    assert repo.get_transaction("new_tx").case_id == "new_case"
                command.check(config)
            finally:
                outer.rollback()
        with engine.connect() as connection:
            assert (
                connection.scalar(
                    text("SELECT count(*) FROM pg_namespace WHERE nspname = :schema"),
                    {"schema": schema},
                )
                == 0
            )
    finally:
        engine.dispose()
