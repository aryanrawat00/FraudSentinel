"""Idempotent, explicit synthetic seed. Never invoked implicitly by API startup."""

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.auth import DEMO_USER_ID
from app.core.config import Settings
from app.db.session import create_db_engine
from app.models import AuditEvent, Case, Evidence, Transaction, User

DEMO_CASE_ID = "case_demo_001"


def seed_demo(session: Session) -> None:
    if session.get(User, DEMO_USER_ID) is None:
        session.add(User(user_id=DEMO_USER_ID, display_name="Demo analyst", role="investigator"))
        session.flush()
    if session.get(Case, DEMO_CASE_ID) is None:
        session.add(
            Case(
                case_id=DEMO_CASE_ID,
                owner_id=DEMO_USER_ID,
                title="Synthetic transfer review",
                status="open",
            )
        )
        session.flush()
    samples = [
        ("001", "1250.00", "2026-11-13T10:30:00+05:30", "device_demo_known"),
        ("002", "2400.00", "2026-11-13T15:10:00+05:30", "device_demo_known"),
        ("003", "800.00", "2026-11-14T11:45:00+05:30", "device_demo_known"),
        ("004", "3100.00", "2026-11-14T17:20:00+05:30", "device_demo_known"),
        ("005", "1850.00", "2026-11-15T12:05:00+05:30", "device_demo_known"),
        ("006", "95000.00", "2026-11-16T02:14:00+05:30", "device_demo_unseen"),
    ]
    for suffix, amount, occurred_at, device in samples:
        transaction_id = f"txn_demo_{suffix}"
        if session.get(Transaction, transaction_id) is None:
            session.add(
                Transaction(
                    transaction_id=transaction_id,
                    case_id=DEMO_CASE_ID,
                    customer_id="customer_demo_001",
                    amount=Decimal(amount),
                    currency="INR",
                    occurred_at=datetime.fromisoformat(occurred_at).astimezone(UTC),
                    device_id=device,
                    beneficiary_id="beneficiary_demo_002"
                    if suffix == "006"
                    else "beneficiary_demo_001",
                )
            )
    session.flush()
    if session.get(Evidence, "evidence_demo_001") is None:
        session.add(
            Evidence(
                evidence_id="evidence_demo_001",
                case_id=DEMO_CASE_ID,
                transaction_id="txn_demo_006",
                source="synthetic_seed_v1",
                description="Synthetic INR 95,000 transfer at 02:14 IST from device_demo_unseen."
                " No fraud classification has been made.",
            )
        )
    if session.get(AuditEvent, "event_demo_seed") is None:
        session.add(
            AuditEvent(
                event_id="event_demo_seed",
                case_id=DEMO_CASE_ID,
                actor_id="development_seed",
                action="SYNTHETIC_DATA_CREATED",
                summary="Created the Phase 1 synthetic demonstration.",
            )
        )


def main() -> None:
    settings = Settings()
    if not settings.demo_mode or settings.app_env == "production":
        raise SystemExit("Seeding requires DEMO_MODE=true in a non-production environment.")
    engine = create_db_engine(settings)
    try:
        with Session(engine) as session, session.begin():
            seed_demo(session)
        print("Synthetic demo seed complete (safe to run again).")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
