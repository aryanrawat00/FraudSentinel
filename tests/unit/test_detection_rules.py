from copy import deepcopy
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.services.detection import Rules, evaluate


def fixtures():
    stamp = datetime(2026, 11, 10, 12, tzinfo=UTC)
    target = dict(
        transaction_id="target",
        source_account_id="a",
        destination_account_id="b",
        customer_id=None,
        amount="100.00",
        currency="INR",
        occurred_at=stamp.isoformat(),
        status="completed",
        transaction_type="transfer",
        device_id="device",
        payment_channel="mobile",
        location={"country_code": "IN"},
    )
    history = [
        {
            **target,
            "transaction_id": f"prior_{i}",
            "occurred_at": (stamp - timedelta(days=i + 1)).isoformat(),
        }
        for i in range(5)
    ]
    return target, history


@pytest.mark.parametrize(
    "score,category",
    [
        ("0", "low"),
        ("24.99", "low"),
        ("25", "medium"),
        ("49.99", "medium"),
        ("50", "high"),
        ("74.99", "high"),
        ("75", "critical"),
        ("100", "critical"),
    ],
)
def test_exact_category_boundaries(score, category):
    assert Rules().category(Decimal(score)) == category


@pytest.mark.parametrize(
    "changes",
    [
        {"amount_ratio": "0"},
        {"amount_ratio": "101"},
        {"medium": "50", "high": "25"},
        {"history_limit": 4},
        {"min_history": 100},
        {"weights": {"AMOUNT_SPIKE": "10"}},
        {"version": "bad version"},
        {"temporal_group_cap": "101"},
    ],
)
def test_invalid_rules_fail_closed(changes):
    with pytest.raises(ValidationError):
        Rules(**changes)


@pytest.mark.parametrize("status", ["failed", "pending", "reversed"])
def test_incomplete_payments_do_not_receive_completed_payment_risk(status):
    target, history = fixtures()
    target.update(status=status, amount="100000.00")
    factors, missing, state = evaluate(target, history, Rules())
    assert factors == [] and missing and state == "insufficient_history"


def test_currency_and_payment_type_are_not_combined_into_amount_baseline():
    target, history = fixtures()
    target.update(amount="100000.00", currency="USD")
    factors, _, status = evaluate(target, history, Rules())
    assert not factors and status == "insufficient_history"
    target.update(currency="INR", transaction_type="refund")
    assert evaluate(target, history, Rules())[0] == []


def test_unavailable_context_does_not_create_context_factors():
    target, history = fixtures()
    target.update(device_id=None, location=None, payment_channel=None)
    factors, missing, _ = evaluate(target, history, Rules())
    assert factors == [] and len(missing) == 3


def test_temporal_factors_share_a_configured_cap_without_inflating_total():
    target, history = fixtures()
    stamp = datetime.fromisoformat(target["occurred_at"])
    for i, row in enumerate(history):
        row.update(
            occurred_at=(stamp - timedelta(minutes=i + 1)).isoformat(),
            destination_account_id=f"dest_{i}",
        )
    factors, _, _ = evaluate(target, history, Rules(temporal_group_cap="27.50"))
    contributions = {f["code"]: Decimal(f["contribution"]) for f in factors}
    assert contributions == {"RAPID_SEQUENCE": Decimal("25"), "RAPID_FANOUT": Decimal("2.50")}


def test_rule_evaluation_does_not_mutate_source_records():
    target, history = fixtures()
    before = deepcopy((target, history))
    evaluate(target, history, Rules())
    assert (target, history) == before


def test_equivalent_timezone_offsets_do_not_change_timing_risk():
    target, history = fixtures()
    target["occurred_at"] = "2026-11-10T17:30:00+05:30"
    assert evaluate(target, history, Rules())[0] == []
