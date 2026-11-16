from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator


class TransactionSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    transaction_id: str
    case_id: str
    customer_id: str
    amount: Decimal
    currency: str
    occurred_at: datetime
    device_id: str
    beneficiary_id: str

    @field_validator("occurred_at")
    @classmethod
    def timezone_required(cls, value: datetime) -> datetime:
        # PostgreSQL preserves timezone information; SQLite test fixtures do not.
        from datetime import UTC

        return value.replace(tzinfo=UTC) if value.tzinfo is None else value


class OverviewResponse(BaseModel):
    mode: Literal["synthetic_demo"] = "synthetic_demo"
    analyst_name: str
    transaction_count: int
    case_count: int
    assessment_count: int
    recent_transactions: list[TransactionSummary]
