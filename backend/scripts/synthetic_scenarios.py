"""Deterministic, clearly synthetic inputs. No claim of real-world accuracy."""

from datetime import UTC, datetime, timedelta

from app.schemas.intelligence import AccountCreate, TransactionCreate
from app.services.detection import DetectionService


def create_scenarios(repo, prefix="scenario"):
    accounts = [f"{prefix}_{key}" for key in ("sender", "recipient", "other", "third")]
    for identifier in accounts:
        repo.create_account(
            AccountCreate(
                account_id=identifier,
                status="active",
                data_source="synthetic_scenarios_v1",
                is_synthetic=True,
            )
        )
    start = datetime(2026, 11, 1, 12, tzinfo=UTC)

    def transfer(name, when, amount="100.00", source=None, destination=None, **extra):
        data = dict(
            transaction_id=f"{prefix}_{name}",
            source_account_id=source or accounts[0],
            destination_account_id=destination or accounts[1],
            amount=amount,
            currency="INR",
            occurred_at=when,
            transaction_type="transfer",
            status="completed",
            device_id=f"{prefix}_device",
            payment_channel="mobile",
            location={"country_code": "IN", "source": "synthetic_fixture"},
            data_source="synthetic_scenarios_v1",
            is_synthetic=True,
        )
        data.update(extra)
        return repo.create_transaction(TransactionCreate(**data)).transaction_id

    for i in range(8):
        transfer(f"baseline_{i}", start + timedelta(days=i))
    normal = transfer("normal", start + timedelta(days=9))
    large = transfer("large", start + timedelta(days=10), "10000.00")
    timing = transfer("timing", start + timedelta(days=10, hours=14))
    for i in range(3):
        transfer(
            f"burst_{i}", start + timedelta(days=11, minutes=i), destination=accounts[1 + i % 3]
        )
    high = transfer(
        "high",
        start + timedelta(days=11, minutes=4),
        "20000.00",
        device_id=f"{prefix}_new_device",
        location={"country_code": "GB", "source": "synthetic_fixture"},
        payment_channel="web",
    )
    transfer("cycle_b", start + timedelta(days=12), source=accounts[1], destination=accounts[2])
    transfer(
        "cycle_c",
        start + timedelta(days=12, minutes=1),
        source=accounts[2],
        destination=accounts[0],
    )
    result = {
        "normal": normal,
        "large": large,
        "timing": timing,
        "high": high,
        "root_account": accounts[0],
    }
    for name in ("normal", "large", "timing", "high"):
        DetectionService(repo).analyze(result[name])
    return result
