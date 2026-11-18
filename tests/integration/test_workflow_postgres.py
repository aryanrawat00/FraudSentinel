"""Upgrade-only PostgreSQL workflow test in a rollback-only random schema."""

import os
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
from app.models.workflow import WorkflowBase
from app.repositories.intelligence import IntelligenceRepository
from app.schemas.workflow import InvestigationCreate
from app.services.detection import DetectionService
from app.services.evidence import EvidenceService
from app.services.investigations import InvestigationService
from scripts.seed_demo_data import seed_demo
from scripts.synthetic_scenarios import create_scenarios

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_PHASE2_POSTGRES_TESTS") != "1", reason="Opt in to rollback-only PostgreSQL tests"
)


def test_upgrade_0003_preserves_all_milestone1_fields_and_persists_full_workflow():
    settings = Settings(_env_file=os.getenv("PHASE2_TEST_ENV_FILE", ".env"))
    engine = create_db_engine(settings)
    config = Config(str(Path(__file__).resolve().parents[2] / "backend/alembic.ini"))
    schema = "workflow_test_" + uuid4().hex
    try:
        with engine.connect() as connection:
            outer = connection.begin()
            try:
                connection.execute(CreateSchema(schema))
                connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))
                assert connection.scalar(text("SELECT current_schema()")) == schema
                config.attributes["connection"] = connection
                command.upgrade(config, "0002_intelligence_contracts")
                with (
                    Session(bind=connection, join_transaction_mode="create_savepoint") as session,
                    session.begin(),
                ):
                    seed_demo(session)
                old = MetaData()
                old.reflect(connection)
                before = {
                    t.name: connection.execute(select(t)).mappings().all()
                    for t in old.sorted_tables
                    if t.name != "alembic_version"
                }
                constraints = {name: inspect(connection).get_foreign_keys(name) for name in before}
                indexes = {name: inspect(connection).get_indexes(name) for name in before}
                command.upgrade(config, "0003_investigation_workflow")
                command.check(config)
                for name, table in WorkflowBase.metadata.tables.items():
                    assert (
                        inspect(connection).get_pk_constraint(name)["name"]
                        == table.primary_key.name
                    )
                    assert {c["name"] for c in inspect(connection).get_foreign_keys(name)} == {
                        c.name for c in table.foreign_key_constraints
                    }
                assert (
                    connection.scalar(text("SELECT version_num FROM alembic_version"))
                    == "0003_investigation_workflow"
                )
                for table in old.sorted_tables:
                    if table.name != "alembic_version":
                        assert (
                            connection.execute(select(table)).mappings().all() == before[table.name]
                        )
                        assert (
                            inspect(connection).get_foreign_keys(table.name)
                            == constraints[table.name]
                        )
                        assert inspect(connection).get_indexes(table.name) == indexes[table.name]
                with (
                    Session(bind=connection, join_transaction_mode="create_savepoint") as session,
                    session.begin(),
                ):
                    repo = IntelligenceRepository(session, "user_demo_analyst")
                    scenarios = create_scenarios(repo)
                    assessment = DetectionService(repo).analyze(scenarios["high"])["assessment"]
                    evidence = EvidenceService(repo).collect(assessment["assessment_id"])
                    service = InvestigationService(repo)
                    service.create(
                        InvestigationCreate(
                            case_id="pg_review",
                            title="PostgreSQL synthetic review",
                            assessment_ids=[assessment["assessment_id"]],
                            evidence_ids=[e.evidence_id for e in evidence],
                        )
                    )
                    report = service.report("pg_review")
                    assert report["content"]["case"]["case_id"] == "pg_review"
                    assert len(report["content"]["evidence"]) == len(evidence)
                    assert len(report["content"]["supporting_source_transactions"]) > 1
                    assert service.report("pg_review")["report_id"] == report["report_id"]
                command.check(config)
            finally:
                outer.rollback()
        with engine.connect() as connection:
            assert (
                connection.scalar(
                    text("SELECT count(*) FROM pg_namespace WHERE nspname=:name"), {"name": schema}
                )
                == 0
            )
    finally:
        engine.dispose()
