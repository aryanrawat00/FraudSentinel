from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Account, CaseAccount, Evidence, RiskAssessment, Transaction, User
from app.repositories.intelligence import (
    AccessDenied,
    Conflict,
    IntelligenceRepository,
    ResourceNotFound,
)
from app.schemas.intelligence import (
    AccountCreate,
    AssessmentCreate,
    CaseCreate,
    EvidenceCreate,
    TransactionCreate,
    TransactionQuery,
)
from scripts.reset_demo import reset_demo
from scripts.seed_demo_data import seed_demo


@pytest.fixture
def repository(engine):
    with Session(engine) as session, session.begin():
        seed_demo(session)
        repo = IntelligenceRepository(session, "user_demo_analyst")
        for identifier in ["account_a", "account_b"]:
            repo.create_account(
                AccountCreate(
                    account_id=identifier,
                    data_source="synthetic_test",
                    is_synthetic=True,
                )
            )
        yield repo


def transfer(identifier="new_transaction", **changes):
    return TransactionCreate(
        **(
            dict(
                transaction_id=identifier,
                source_account_id="account_a",
                destination_account_id="account_b",
                amount="45.67",
                currency="USD",
                occurred_at="2026-11-17T10:00:00Z",
                transaction_type="transfer",
                status="completed",
                data_source="synthetic_test",
                is_synthetic=True,
            )
            | changes
        )
    )


def assessment(identifier="assessment1", transaction_id="new_transaction"):
    return AssessmentCreate(
        assessment_id=identifier,
        transaction_id=transaction_id,
        score="40.25",
        risk_category="medium",
        method="rules",
        ruleset_version="test_only_v1",
        status="complete",
        factors=[
            {
                "code": "TEST_ONLY",
                "description": "Persistence test, not a detector result",
                "contribution": "40.25",
                "source_transaction_ids": [transaction_id],
                "review_guidance": "Synthetic test fixture only",
            }
        ],
    )


def evidence(**changes):
    return EvidenceCreate(
        **(
            dict(
                evidence_id="evidence_new",
                transaction_id="new_transaction",
                assessment_id="assessment1",
                description="Synthetic persistence test",
                source="test_fixture",
                kind="derived_indicator",
                method="test_only_v1",
                provenance={
                    "source_reference": "fixture:1",
                    "source_transaction_ids": ["new_transaction"],
                    "observed_at": "2026-11-17T10:00:00Z",
                },
            )
            | changes
        )
    )


def test_ingestion_precedes_case_and_preserves_missing_context(repository):
    created = repository.create_transaction(transfer())
    assert created.case_id is None and created.device_id is None and created.location is None
    assert created.currency == "USD" and created.amount == Decimal("45.67")
    assert repository.get_transaction(created.transaction_id).model_dump() == created.model_dump()
    assert repository.get_transaction("txn_demo_006").source_account_id is None


def test_history_retains_prior_assessments_and_roundtrips_score_scale(repository):
    repository.create_transaction(transfer())
    first = repository.record_assessment(assessment())
    repository.record_assessment(assessment("assessment2"))
    assert first.score == Decimal("40.25")
    assert repository.session.get(RiskAssessment, first.assessment_id).risk_score == Decimal(
        "0.4025"
    )
    assert len(repository.list_assessments("new_transaction")) == 2
    with pytest.raises(Conflict):
        repository.record_assessment(assessment())
    assert len(repository.list_assessments("new_transaction")) == 2


def test_evidence_can_precede_case_and_never_claims_independent_verification(repository):
    repository.create_transaction(transfer())
    repository.record_assessment(assessment())
    saved = repository.create_evidence(evidence())
    assert saved.case_id is None and saved.verification_status == "unverified"
    assert saved.provenance.source_transaction_ids == ["new_transaction"]
    assert repository.get_evidence(saved.evidence_id).model_dump() == saved.model_dump()
    assert repository.get_evidence("evidence_demo_001").provenance is None


def test_case_associations_are_idempotent_and_refuse_reassignment(repository):
    repository.create_transaction(transfer())
    repository.create_case(CaseCreate(case_id="new_case", title="Review synthetic transfer"))
    repository.attach_transaction("new_case", "new_transaction")
    repository.attach_account("new_case", "account_a")
    repository.attach_account("new_case", "account_a")
    assert repository.session.scalar(select(func.count()).select_from(CaseAccount)) == 1
    with pytest.raises(Conflict):
        repository.attach_transaction("case_demo_001", "new_transaction")
    assert repository.get_transaction("new_transaction").case_id == "new_case"


def test_queries_are_scoped_paginated_and_use_exclusive_end_times(repository):
    repository.create_transaction(transfer("new_a"))
    repository.create_transaction(transfer("new_b", occurred_at="2026-11-18T10:00:00Z"))
    query = TransactionQuery(account_id="account_a", currency="USD", limit=1)
    assert [row.transaction_id for row in repository.list_transactions(query)] == ["new_b"]
    query.offset = 1
    assert [row.transaction_id for row in repository.list_transactions(query)] == ["new_a"]
    window = TransactionQuery(
        occurred_from="2026-11-17T10:00:00Z", occurred_before="2026-11-18T10:00:00Z"
    )
    assert [row.transaction_id for row in repository.list_transactions(window)] == ["new_a"]


def test_other_principals_cannot_read_or_link_dataset_resources(repository):
    repository.create_transaction(transfer())
    repository.record_assessment(assessment())
    repository.create_evidence(evidence())
    repository.session.add(User(user_id="other", display_name="Other", role="investigator"))
    repository.session.flush()
    other = IntelligenceRepository(repository.session, "other")
    assert other.list_transactions(TransactionQuery()) == []
    with pytest.raises(ResourceNotFound):
        other.get_transaction("new_transaction")
    with pytest.raises(ResourceNotFound):
        other.create_transaction(transfer("cross_scope"))
    with pytest.raises(ResourceNotFound):
        other.attach_account("case_demo_001", "account_a")
    with pytest.raises(ResourceNotFound):
        other.get_evidence("evidence_new")
    with pytest.raises(ResourceNotFound):
        other.list_assessments("new_transaction")


def test_reviewer_and_unknown_principals_cannot_write(repository):
    repository.session.add(User(user_id="reader", display_name="Reader", role="reviewer"))
    repository.session.flush()
    reader = IntelligenceRepository(repository.session, "reader")
    with pytest.raises(AccessDenied):
        reader.create_case(CaseCreate(case_id="forbidden", title="Denied"))
    with pytest.raises(AccessDenied):
        IntelligenceRepository(repository.session, "missing")


def test_evidence_rejects_mismatched_assessments_and_cases(repository):
    repository.create_transaction(transfer())
    repository.record_assessment(assessment())
    repository.create_transaction(transfer("other_tx"))
    with pytest.raises(Conflict):
        repository.create_evidence(evidence(case_id="case_demo_001"))
    repository.record_assessment(assessment("other_assessment", "other_tx"))
    with pytest.raises(Conflict):
        repository.create_evidence(evidence(assessment_id="other_assessment"))


def test_database_itself_rejects_cross_scope_account_references(repository):
    repository.session.add(User(user_id="other", display_name="Other", role="investigator"))
    repository.session.flush()
    repository.session.add(
        Account(
            account_id="private",
            owner_id="other",
            status="active",
            data_source="synthetic",
            is_synthetic=True,
        )
    )
    repository.session.flush()
    with pytest.raises(IntegrityError), repository.session.begin_nested():
        values = transfer("bad_fk").model_dump(exclude={"location"})
        values["source_account_id"] = "private"
        repository.session.add(Transaction(**values, owner_id="user_demo_analyst"))
        repository.session.flush()


def test_database_itself_rejects_evidence_for_wrong_assessed_transaction(repository):
    repository.create_transaction(transfer())
    repository.create_transaction(transfer("other_tx"))
    repository.record_assessment(assessment())
    with pytest.raises(IntegrityError), repository.session.begin_nested():
        repository.session.add(
            Evidence(
                evidence_id="bad_fk",
                transaction_id="other_tx",
                assessment_id="assessment1",
                description="Invalid fixture",
                source="test",
            )
        )
        repository.session.flush()


def test_transaction_rollback_does_not_leave_partial_ingestion(engine):
    with Session(engine) as session, session.begin():
        seed_demo(session)
    with pytest.raises(RuntimeError), Session(engine) as session, session.begin():
        repo = IntelligenceRepository(session, "user_demo_analyst")
        repo.create_account(
            AccountCreate(account_id="rolled_back", data_source="test", is_synthetic=True)
        )
        raise RuntimeError("Simulated import failure")
    with Session(engine) as session:
        assert session.get(Account, "rolled_back") is None


def test_explicit_demo_reset_preserves_accounts_and_handles_new_case_links(repository):
    repository.create_transaction(transfer())
    repository.record_assessment(assessment())
    repository.create_evidence(evidence())
    repository.attach_transaction("case_demo_001", "new_transaction")
    repository.attach_account("case_demo_001", "account_a")
    reset_demo(repository.session)
    assert repository.session.get(Transaction, "new_transaction") is None
    assert repository.session.get(Evidence, "evidence_new") is None
    assert repository.session.get(Account, "account_a") is not None
    assert repository.session.scalar(select(func.count()).select_from(CaseAccount)) == 0
    assert repository.get_transaction("txn_demo_006").amount == Decimal("95000.00")


def test_supporting_references_cannot_import_another_principals_records(repository):
    repository.create_transaction(transfer())
    repository.record_assessment(assessment())
    repository.session.add(User(user_id="other", display_name="Other", role="investigator"))
    repository.session.flush()
    other = IntelligenceRepository(repository.session, "other")
    for identifier in ["private_source", "private_destination"]:
        other.create_account(
            AccountCreate(account_id=identifier, data_source="test", is_synthetic=True)
        )
    other.create_transaction(
        transfer(
            "private_tx",
            source_account_id="private_source",
            destination_account_id="private_destination",
        )
    )
    invalid_assessment = assessment("invalid_support")
    invalid_assessment.factors[0].source_transaction_ids = ["private_tx"]
    with pytest.raises(ResourceNotFound):
        repository.record_assessment(invalid_assessment)
    invalid_evidence = evidence()
    invalid_evidence.provenance.source_transaction_ids.append("private_tx")
    with pytest.raises(ResourceNotFound):
        repository.create_evidence(invalid_evidence)
