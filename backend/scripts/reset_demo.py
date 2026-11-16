"""Reset only the reserved synthetic demonstration case, with explicit confirmation."""

import argparse

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.session import create_db_engine
from app.models import (
    AgentRequest,
    AuditEvent,
    Case,
    Evidence,
    PolicyDecision,
    RiskAssessment,
    Transaction,
)
from scripts.seed_demo_data import DEMO_CASE_ID, DEMO_USER_ID, seed_demo


def reset_demo(session: Session) -> None:
    case = session.get(Case, DEMO_CASE_ID)
    if case is not None and case.owner_id != DEMO_USER_ID:
        raise ValueError("Reserved demo case has an unexpected owner; reset refused")
    request_ids = select(AgentRequest.request_id).where(AgentRequest.case_id == DEMO_CASE_ID)
    transaction_ids = select(Transaction.transaction_id).where(Transaction.case_id == DEMO_CASE_ID)
    session.execute(delete(PolicyDecision).where(PolicyDecision.request_id.in_(request_ids)))
    session.execute(delete(AuditEvent).where(AuditEvent.case_id == DEMO_CASE_ID))
    session.execute(delete(AgentRequest).where(AgentRequest.case_id == DEMO_CASE_ID))
    session.execute(delete(Evidence).where(Evidence.case_id == DEMO_CASE_ID))
    session.execute(
        delete(RiskAssessment).where(RiskAssessment.transaction_id.in_(transaction_ids))
    )
    session.execute(delete(Transaction).where(Transaction.case_id == DEMO_CASE_ID))
    session.execute(delete(Case).where(Case.case_id == DEMO_CASE_ID))
    session.flush()
    session.expire_all()
    seed_demo(session)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--confirm-synthetic-reset", action="store_true")
    args = parser.parse_args()
    settings = Settings()
    if not args.confirm_synthetic_reset:
        parser.error("Pass --confirm-synthetic-reset to recreate case_demo_001 and its records")
    if not settings.demo_mode or settings.app_env == "production":
        raise SystemExit("Reset requires DEMO_MODE=true in a non-production environment.")
    engine = create_db_engine(settings)
    try:
        with Session(engine) as session, session.begin():
            reset_demo(session)
        print("Synthetic case reset. Unrelated cases were preserved.")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
