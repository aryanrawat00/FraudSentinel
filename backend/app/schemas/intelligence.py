"""Phase 2 contracts. These do not expose unauthenticated write endpoints."""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import (
    AfterValidator,
    AwareDatetime,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    StrictBool,
    model_validator,
)


def decimal_input(value):
    if not isinstance(value, (str, Decimal)):
        raise ValueError("Use a decimal string, not a binary floating-point number")
    return value


def timestamp_input(value):
    if not isinstance(value, (str, datetime)):
        raise ValueError("Use a timezone-aware ISO 8601 timestamp")
    if isinstance(value, str) and "T" not in value:
        raise ValueError("Use an ISO 8601 timestamp, not an epoch or date-only value")
    return value


Identifier = Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,63}$")]
Currency = Annotated[str, Field(pattern=r"^[A-Z]{3}$")]
Money = Annotated[
    Decimal,
    Field(gt=0, max_digits=14, decimal_places=2, allow_inf_nan=False),
    BeforeValidator(decimal_input),
]
Score = Annotated[
    Decimal,
    Field(ge=0, le=100, max_digits=5, decimal_places=2, allow_inf_nan=False),
    BeforeValidator(decimal_input),
]
Timestamp = Annotated[
    AwareDatetime,
    BeforeValidator(timestamp_input),
    AfterValidator(lambda value: value.astimezone(UTC)),
]
RiskCategory = Literal["low", "medium", "high", "critical"]
Description = Annotated[str, Field(min_length=1, max_length=500)]


class Contract(BaseModel):
    model_config = ConfigDict(
        extra="forbid", str_strip_whitespace=True, from_attributes=True, validate_assignment=True
    )


class AccountCreate(Contract):
    account_id: Identifier
    status: Literal["unknown", "active", "inactive", "closed"] = "unknown"
    opened_at: Timestamp | None = None
    data_source: Annotated[str, Field(min_length=1, max_length=100)]
    is_synthetic: StrictBool


class AccountRead(AccountCreate):
    created_at: Timestamp


class Location(Contract):
    country_code: Annotated[str, Field(pattern=r"^[A-Z]{2}$")] | None = None
    latitude: Annotated[Decimal, Field(ge=-90, le=90, allow_inf_nan=False)] | None = None
    longitude: Annotated[Decimal, Field(ge=-180, le=180, allow_inf_nan=False)] | None = None
    source: Annotated[str, Field(min_length=1, max_length=100)]

    @model_validator(mode="after")
    def coordinates_are_paired(self):
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("Latitude and longitude must be supplied together")
        if self.country_code is None and self.latitude is None:
            raise ValueError("Location must contain an observed country or coordinates")
        return self


class TransactionCreate(Contract):
    transaction_id: Identifier
    source_account_id: Identifier
    destination_account_id: Identifier
    amount: Money
    currency: Currency
    occurred_at: Timestamp
    transaction_type: Literal["transfer", "payment", "refund", "deposit", "withdrawal"]
    status: Literal["pending", "completed", "failed", "reversed"]
    payment_channel: Annotated[str, Field(min_length=1, max_length=32)] | None = None
    device_id: Identifier | None = None
    location: Location | None = None
    data_source: Annotated[str, Field(min_length=1, max_length=100)]
    is_synthetic: StrictBool


class TransactionRead(Contract):
    transaction_id: Identifier
    case_id: Identifier | None
    source_account_id: Identifier | None
    destination_account_id: Identifier | None
    amount: Money
    currency: Currency
    occurred_at: Timestamp
    transaction_type: str
    status: str
    payment_channel: str | None
    device_id: str | None
    location: Location | None
    data_source: str
    is_synthetic: bool | None
    created_at: Timestamp | None


class TransactionQuery(Contract):
    limit: Annotated[int, Field(ge=1, le=100)] = 25
    offset: Annotated[int, Field(ge=0, le=10000)] = 0
    account_id: Identifier | None = None
    currency: Currency | None = None
    occurred_from: Timestamp | None = None
    occurred_before: Timestamp | None = None

    @model_validator(mode="after")
    def valid_window(self):
        if self.occurred_from and self.occurred_before:
            if self.occurred_from >= self.occurred_before:
                raise ValueError("Start must precede end; time windows are [start, end)")
        return self


class CaseCreate(Contract):
    case_id: Identifier
    title: Annotated[str, Field(min_length=1, max_length=200)]
    description: Annotated[str, Field(max_length=5000)] = ""
    priority: Literal["low", "medium", "high", "urgent"] = "medium"


class CaseRead(CaseCreate):
    status: Literal["open", "in_review", "closed"]
    created_at: Timestamp
    updated_at: Timestamp | None


class RiskFactor(Contract):
    code: Identifier
    description: Description
    contribution: Score
    source_transaction_ids: Annotated[list[Identifier], Field(min_length=1, max_length=100)]
    review_guidance: Description


class AssessmentCreate(Contract):
    assessment_id: Identifier
    transaction_id: Identifier
    score: Score
    risk_category: RiskCategory
    method: Literal["rules", "statistical", "hybrid"]
    ruleset_version: Identifier
    status: Literal["complete", "insufficient_history"]
    factors: Annotated[list[RiskFactor], Field(max_length=32)]
    missing_information: Annotated[list[Description], Field(max_length=32)] = Field(
        default_factory=list
    )

    @model_validator(mode="after")
    def explain_total(self):
        if sum((factor.contribution for factor in self.factors), Decimal(0)) != self.score:
            raise ValueError("Factor contributions must sum exactly to the score")
        if len({factor.code for factor in self.factors}) != len(self.factors):
            raise ValueError("Factor codes must be unique")
        if self.status == "insufficient_history" and not self.missing_information:
            raise ValueError("Insufficient history must explain what is missing")
        return self


class AssessmentRead(Contract):
    assessment_id: Identifier
    transaction_id: Identifier
    score: Score
    risk_category: RiskCategory | None
    method: str
    ruleset_version: str
    status: str
    factors: list[RiskFactor]
    missing_information: list[str]
    created_at: Timestamp


class Provenance(Contract):
    source_reference: Annotated[str, Field(min_length=1, max_length=200)]
    source_transaction_ids: Annotated[list[Identifier], Field(min_length=1, max_length=100)]
    observed_at: Timestamp


class EvidenceCreate(Contract):
    evidence_id: Identifier
    transaction_id: Identifier
    case_id: Identifier | None = None
    assessment_id: Identifier | None = None
    account_id: Identifier | None = None
    description: Description
    source: Annotated[str, Field(min_length=1, max_length=100)]
    kind: Literal["observed_fact", "derived_indicator", "ai_interpretation"]
    method: Identifier
    provenance: Provenance

    @model_validator(mode="after")
    def require_association(self):
        if self.case_id is None and self.assessment_id is None:
            raise ValueError("Evidence must reference a case or assessment")
        if self.transaction_id not in self.provenance.source_transaction_ids:
            raise ValueError("Provenance must include the primary source transaction")
        return self


class EvidenceRead(Contract):
    evidence_id: Identifier
    transaction_id: Identifier
    case_id: Identifier | None
    assessment_id: Identifier | None
    account_id: Identifier | None
    description: str
    source: str
    kind: str
    method: str
    verification_status: str
    provenance: Provenance | None
    captured_at: Timestamp
