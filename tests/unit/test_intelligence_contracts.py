from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.schemas.intelligence import (
    AssessmentCreate,
    EvidenceCreate,
    Location,
    TransactionCreate,
    TransactionQuery,
)


def transaction(**changes):
    return (
        dict(
            transaction_id="tx_1",
            source_account_id="acct_a",
            destination_account_id="acct_b",
            amount="12.34",
            currency="USD",
            occurred_at="2026-11-17T02:14:00+05:30",
            transaction_type="transfer",
            status="completed",
            data_source="synthetic_test",
            is_synthetic=True,
        )
        | changes
    )


@pytest.mark.parametrize(
    "amount", ["0", "-1", "NaN", "Infinity", "1.001", "1000000000000", 1.2, True]
)
def test_invalid_money_never_silently_rounds_or_accepts_binary_floats(amount):
    with pytest.raises(ValidationError):
        TransactionCreate(**transaction(amount=amount))


@pytest.mark.parametrize("currency", ["usd", "US", "USDD", "123"])
def test_currency_requires_an_explicit_three_letter_code(currency):
    with pytest.raises(ValidationError):
        TransactionCreate(**transaction(currency=currency))


@pytest.mark.parametrize(
    "timestamp",
    [
        "2026-11-17T01:00:00",
        "not-a-date",
        1234567,
        "1234567",
        "2026-11-17",
    ],
)
def test_timestamp_requires_a_valid_explicit_timezone(timestamp):
    with pytest.raises(ValidationError):
        TransactionCreate(**transaction(occurred_at=timestamp))


def test_transaction_preserves_decimal_currency_and_normalizes_time_without_context_fabrication():
    data = TransactionCreate(**transaction())
    assert data.amount == Decimal("12.34")
    assert data.currency == "USD"
    assert data.model_dump(mode="json")["occurred_at"] == "2026-11-16T20:44:00Z"
    assert data.location is None and data.device_id is None


@pytest.mark.parametrize("field", ["owner_id", "role", "case_id", "access_token"])
def test_ingestion_contract_cannot_set_privileged_fields(field):
    with pytest.raises(ValidationError):
        TransactionCreate(**transaction(**{field: "caller_controlled"}))


def test_location_requires_observed_coordinates_and_provenance():
    with pytest.raises(ValidationError):
        Location(source="fixture", latitude="12")
    with pytest.raises(ValidationError):
        Location(source="fixture", latitude="91", longitude="5")
    with pytest.raises(ValidationError):
        Location(source="fixture")
    assert Location(source="fixture", country_code="IN").latitude is None


@pytest.mark.parametrize(
    "query",
    [
        {"limit": 101},
        {"offset": -1},
        {
            "occurred_from": "2026-11-17T00:00:00Z",
            "occurred_before": "2026-11-17T00:00:00Z",
        },
    ],
)
def test_query_limits_and_time_windows_are_bounded(query):
    with pytest.raises(ValidationError):
        TransactionQuery(**query)


def test_assessment_requires_contributions_and_missing_history_explanation():
    values = dict(
        assessment_id="assessment_1",
        transaction_id="tx_1",
        score="50",
        risk_category="medium",
        method="rules",
        ruleset_version="test_v1",
        status="complete",
        factors=[],
    )
    with pytest.raises(ValidationError, match="sum exactly"):
        AssessmentCreate(**values)
    with pytest.raises(ValidationError, match="what is missing"):
        AssessmentCreate(**(values | {"score": "0", "status": "insufficient_history"}))
    data = AssessmentCreate(
        **(
            values
            | {
                "score": "0",
                "risk_category": "low",
                "status": "insufficient_history",
                "missing_information": ["Fewer than the configured number of prior transfers"],
            }
        )
    )
    assert data.score == 0 and not data.factors


def test_evidence_cannot_be_unassociated_or_claim_verified_status():
    values = dict(
        evidence_id="ev1",
        transaction_id="tx_1",
        description="Observed transfer",
        source="fixture",
        kind="observed_fact",
        method="import_v1",
        provenance={
            "source_reference": "fixture:row1",
            "source_transaction_ids": ["tx_1"],
            "observed_at": "2026-11-17T00:00:00Z",
        },
    )
    with pytest.raises(ValidationError, match="case or assessment"):
        EvidenceCreate(**values)
    with pytest.raises(ValidationError):
        EvidenceCreate(**(values | {"case_id": "case1", "verification_status": "verified"}))
    with pytest.raises(ValidationError, match="primary source"):
        EvidenceCreate(
            **(
                values
                | {
                    "case_id": "case1",
                    "provenance": {
                        **values["provenance"],
                        "source_transaction_ids": ["different_transaction"],
                    },
                }
            )
        )
