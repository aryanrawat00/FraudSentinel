"""Additive milestone 2-4 tables; kept separate until migration activation."""

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    MetaData,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.db.base import Base
from app.models.records import Case, Evidence, RiskAssessment, User, utc_now


class WorkflowBase(DeclarativeBase):
    metadata = MetaData(naming_convention=Base.metadata.naming_convention)


class AnalysisRun(WorkflowBase):
    __tablename__ = "analysis_runs"
    assessment_id: Mapped[str] = mapped_column(
        ForeignKey(RiskAssessment.assessment_id), primary_key=True
    )
    fingerprint: Mapped[str] = mapped_column(String(64), unique=True)
    snapshot: Mapped[dict] = mapped_column(JSON)


class CaseWorkflow(WorkflowBase):
    __tablename__ = "case_workflows"
    __table_args__ = (
        ForeignKeyConstraint(
            ["case_id", "owner_id"], [Case.case_id, Case.owner_id], name="fk_case_workflows_scope"
        ),
        CheckConstraint(
            "status IN ('open','under_investigation','pending_review','resolved','closed')",
            name="status",
        ),
        CheckConstraint("version >= 1", name="version"),
    )
    case_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    owner_id: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(32), default="open")
    assigned_to: Mapped[str | None] = mapped_column(ForeignKey(User.user_id))
    version: Mapped[int] = mapped_column(Integer, default=1)


class CaseEvent(WorkflowBase):
    __tablename__ = "case_events"
    event_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    case_id: Mapped[str] = mapped_column(ForeignKey(Case.case_id), index=True)
    actor_id: Mapped[str] = mapped_column(ForeignKey(User.user_id))
    kind: Mapped[str] = mapped_column(String(40))
    description: Mapped[str] = mapped_column(Text)
    references: Mapped[dict] = mapped_column(JSON)
    created_at = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class InvestigationReport(WorkflowBase):
    __tablename__ = "investigation_reports"
    report_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    case_id: Mapped[str] = mapped_column(ForeignKey(Case.case_id), index=True)
    fingerprint: Mapped[str] = mapped_column(String(64), unique=True)
    content: Mapped[dict] = mapped_column(JSON)
    created_at = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class EvidenceFingerprint(WorkflowBase):
    __tablename__ = "evidence_fingerprints"
    evidence_id: Mapped[str] = mapped_column(ForeignKey(Evidence.evidence_id), primary_key=True)
    fingerprint: Mapped[str] = mapped_column(String(64), unique=True)
