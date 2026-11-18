from typing import Annotated, Literal

from pydantic import Field, model_validator

from app.schemas.intelligence import (
    AssessmentRead,
    CaseCreate,
    Contract,
    EvidenceRead,
    Identifier,
    Timestamp,
    TransactionRead,
)

WorkflowStatus = Literal["open", "under_investigation", "pending_review", "resolved", "closed"]


class Page(Contract):
    limit: Annotated[int, Field(ge=1, le=100)] = 25
    offset: Annotated[int, Field(ge=0, le=10000)] = 0


class GraphQuery(Contract):
    depth: Annotated[int, Field(ge=1, le=3)] = 2
    limit: Annotated[int, Field(ge=1, le=100)] = 100
    occurred_from: Timestamp | None = None
    occurred_before: Timestamp | None = None

    @model_validator(mode="after")
    def window(self):
        if (
            self.occurred_from
            and self.occurred_before
            and self.occurred_from >= self.occurred_before
        ):
            raise ValueError("Start must precede end")
        return self


class InvestigationCreate(CaseCreate):
    transaction_ids: Annotated[list[Identifier], Field(max_length=100)] = Field(
        default_factory=list
    )
    assessment_ids: Annotated[list[Identifier], Field(max_length=100)] = Field(default_factory=list)
    account_ids: Annotated[list[Identifier], Field(max_length=100)] = Field(default_factory=list)
    evidence_ids: Annotated[list[Identifier], Field(max_length=100)] = Field(default_factory=list)


class CasePatch(Contract):
    expected_version: Annotated[int, Field(ge=1)]
    title: Annotated[str, Field(min_length=1, max_length=200)] | None = None
    description: Annotated[str, Field(max_length=5000)] | None = None
    priority: Literal["low", "medium", "high", "urgent"] | None = None
    status: WorkflowStatus | None = None
    assigned_to: Identifier | None = None


class NoteCreate(Contract):
    text: Annotated[str, Field(min_length=1, max_length=5000)]


class CaseLinks(Contract):
    transaction_ids: Annotated[list[Identifier], Field(max_length=100)] = Field(
        default_factory=list
    )
    assessment_ids: Annotated[list[Identifier], Field(max_length=100)] = Field(default_factory=list)
    account_ids: Annotated[list[Identifier], Field(max_length=100)] = Field(default_factory=list)
    evidence_ids: Annotated[list[Identifier], Field(max_length=100)] = Field(default_factory=list)


class InvestigationRead(CaseCreate):
    status: WorkflowStatus
    legacy_status: Literal["open", "in_review", "closed"]
    version: int
    assigned_to: Identifier | None
    created_at: Timestamp
    updated_at: Timestamp | None


class EventRead(Contract):
    event_id: Identifier
    case_id: Identifier
    actor_id: Identifier
    kind: str
    description: str
    references: dict
    created_at: Timestamp


class TransactionDetail(Contract):
    transaction: TransactionRead
    assessments: list[AssessmentRead]
    evidence: list[EvidenceRead]


class AnalysisRead(Contract):
    assessment: AssessmentRead
    analysis: dict | None
    fingerprint: str | None


class ReportSummary(Contract):
    report_id: Identifier
    created_at: Timestamp
    fingerprint: str


class ReportRead(ReportSummary):
    case_id: Identifier
    content: dict


class DashboardRead(Contract):
    transaction_count: int
    suspicious_count: int
    open_investigations: int
    risk_distribution: dict[str, int]
    recent_high_risk: list[TransactionRead]
    recent_activity: list[EventRead]
