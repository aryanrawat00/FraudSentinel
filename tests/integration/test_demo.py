from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import AuditEvent, Case, Evidence, Transaction, User
from scripts.reset_demo import reset_demo
from scripts.seed_demo_data import seed_demo


def test_unseeded_demo_returns_actionable_response(client):
    assert client.get("/api/v1/demo/overview").status_code == 409


def test_seed_is_repeatable_and_api_returns_persisted_data(client, engine):
    with Session(engine) as session, session.begin():
        seed_demo(session)
        seed_demo(session)
    response = client.get("/api/v1/demo/overview")
    assert response.status_code == 200
    data = response.json()
    assert data["transaction_count"] == 6
    assert data["case_count"] == 1
    assert data["assessment_count"] == 0
    transaction = data["recent_transactions"][0]
    assert transaction["transaction_id"] == "txn_demo_006"
    assert transaction["amount"] == "95000.00"
    assert transaction["occurred_at"] == "2026-11-15T20:44:00Z"
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(Evidence)) == 1
        assert session.scalar(select(func.count()).select_from(AuditEvent)) == 1


def test_demo_overview_does_not_include_other_analysts_cases(client, engine):
    with Session(engine) as session, session.begin():
        seed_demo(session)
        session.add(User(user_id="other_analyst", display_name="Other", role="investigator"))
        session.flush()
        session.add(Case(case_id="other_case", title="Unrelated", owner_id="other_analyst"))
        session.flush()
        session.add(
            Transaction(
                transaction_id="other_transaction",
                case_id="other_case",
                customer_id="other_customer",
                amount=Decimal("10.00"),
                currency="INR",
                occurred_at=datetime.now(UTC),
                device_id="other_device",
                beneficiary_id="other_beneficiary",
            )
        )
    response = client.get("/api/v1/demo/overview", headers={"X-User-Id": "other_analyst"})
    assert response.status_code == 200
    assert response.json()["transaction_count"] == 6
    assert "other_customer" not in response.text


def test_evidence_cannot_reference_a_transaction_from_another_case(engine):
    with Session(engine) as session, session.begin():
        seed_demo(session)
        session.add(Case(case_id="case_other", title="Other", owner_id="user_demo_analyst"))
    with Session(engine) as session:
        session.add(
            Evidence(
                evidence_id="invalid",
                case_id="case_other",
                transaction_id="txn_demo_006",
                description="Cross-case evidence must fail",
                source="test",
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()


def test_reset_preserves_unrelated_cases(client, engine):
    with Session(engine) as session, session.begin():
        seed_demo(session)
        session.add(User(user_id="unrelated", display_name="Other", role="investigator"))
        session.flush()
        session.add(Case(case_id="preserve_me", title="Other", owner_id="unrelated"))
        session.flush()
        transaction = session.get(Transaction, "txn_demo_006")
        transaction.amount = Decimal("123.00")
        session.flush()
        reset_demo(session)
    with Session(engine) as session:
        assert session.get(Case, "preserve_me") is not None
        assert session.get(Transaction, "txn_demo_006").amount == Decimal("95000.00")
    assert client.get("/api/v1/demo/overview").json()["transaction_count"] == 6
