from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.auth import require_demo_identity
from app.db.session import get_session
from app.models import Case, RiskAssessment, Transaction, User
from app.schemas.overview import OverviewResponse, TransactionSummary

router = APIRouter(prefix="/demo", tags=["synthetic demo"])


@router.get("/overview", response_model=OverviewResponse)
def overview(
    user_id: Annotated[str, Depends(require_demo_identity)],
    session: Annotated[Session, Depends(get_session)],
) -> OverviewResponse:
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=409, detail="Demo data has not been seeded")
    if user.role != "investigator":
        raise HTTPException(status_code=403, detail="Demo investigator access is required")
    owned_cases = select(Case.case_id).where(Case.owner_id == user_id)
    scoped_transactions = select(Transaction.transaction_id).where(
        Transaction.case_id.in_(owned_cases)
    )
    recent = session.scalars(
        select(Transaction)
        .where(Transaction.case_id.in_(owned_cases))
        .order_by(Transaction.occurred_at.desc(), Transaction.transaction_id)
        .limit(6)
    ).all()
    return OverviewResponse(
        analyst_name=user.display_name,
        transaction_count=session.scalar(
            select(func.count())
            .select_from(Transaction)
            .where(Transaction.case_id.in_(owned_cases))
        )
        or 0,
        case_count=session.scalar(
            select(func.count()).select_from(Case).where(Case.owner_id == user_id)
        )
        or 0,
        assessment_count=session.scalar(
            select(func.count())
            .select_from(RiskAssessment)
            .where(RiskAssessment.transaction_id.in_(scoped_transactions))
        )
        or 0,
        recent_transactions=[TransactionSummary.model_validate(row) for row in recent],
    )
