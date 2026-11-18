from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def utc_now() -> datetime:
    return datetime.now(UTC)


class User(Base):
    __tablename__ = "users"
    user_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(100))
    role: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class Case(Base):
    __tablename__ = "cases"
    __table_args__ = (
        CheckConstraint("status IN ('open', 'in_review', 'closed')", name="status"),
        CheckConstraint("priority IN ('low', 'medium', 'high', 'urgent')", name="priority"),
        UniqueConstraint("case_id", "owner_id", name="uq_cases_case_owner"),
    )
    case_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.user_id"), index=True)
    status: Mapped[str] = mapped_column(String(32), default="open")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    description: Mapped[str] = mapped_column(Text, default="", server_default="")
    priority: Mapped[str] = mapped_column(String(16), default="medium", server_default="medium")
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Account(Base):
    """An account reference within an investigator's dataset, without personal details."""

    __tablename__ = "accounts"
    __table_args__ = (
        UniqueConstraint("account_id", "owner_id", name="uq_accounts_account_owner"),
        CheckConstraint("status IN ('unknown', 'active', 'inactive', 'closed')", name="status"),
    )
    account_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.user_id"), index=True)
    status: Mapped[str] = mapped_column(String(16), default="unknown")
    opened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    data_source: Mapped[str] = mapped_column(String(100))
    is_synthetic: Mapped[bool] = mapped_column(Boolean)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class CaseAccount(Base):
    __tablename__ = "case_accounts"
    __table_args__ = (
        ForeignKeyConstraint(
            ["case_id", "owner_id"],
            ["cases.case_id", "cases.owner_id"],
            name="fk_case_accounts_case_scope",
        ),
        ForeignKeyConstraint(
            ["account_id", "owner_id"],
            ["accounts.account_id", "accounts.owner_id"],
            name="fk_case_accounts_account_scope",
        ),
    )
    case_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    account_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    owner_id: Mapped[str] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = (
        CheckConstraint("amount > 0", name="positive_amount"),
        UniqueConstraint("transaction_id", "case_id"),
        CheckConstraint("owner_id IS NOT NULL OR case_id IS NOT NULL", name="access_scope"),
        CheckConstraint(
            "(source_account_id IS NULL AND destination_account_id IS NULL) OR "
            "(source_account_id IS NOT NULL AND destination_account_id IS NOT NULL "
            "AND owner_id IS NOT NULL)",
            name="account_pair",
        ),
        ForeignKeyConstraint(
            ["case_id", "owner_id"],
            ["cases.case_id", "cases.owner_id"],
            name="fk_transactions_case_scope",
        ),
        ForeignKeyConstraint(
            ["source_account_id", "owner_id"],
            ["accounts.account_id", "accounts.owner_id"],
            name="fk_transactions_source_scope",
        ),
        ForeignKeyConstraint(
            ["destination_account_id", "owner_id"],
            ["accounts.account_id", "accounts.owner_id"],
            name="fk_transactions_destination_scope",
        ),
    )
    transaction_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    case_id: Mapped[str | None] = mapped_column(ForeignKey("cases.case_id"), index=True)
    customer_id: Mapped[str | None] = mapped_column(String(64), index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    device_id: Mapped[str | None] = mapped_column(String(64))
    beneficiary_id: Mapped[str | None] = mapped_column(String(64))
    owner_id: Mapped[str | None] = mapped_column(ForeignKey("users.user_id"), index=True)
    source_account_id: Mapped[str | None] = mapped_column(String(64), index=True)
    destination_account_id: Mapped[str | None] = mapped_column(String(64), index=True)
    transaction_type: Mapped[str] = mapped_column(
        String(24), default="unknown", server_default="unknown"
    )
    status: Mapped[str] = mapped_column(String(24), default="unknown", server_default="unknown")
    payment_channel: Mapped[str | None] = mapped_column(String(32))
    location: Mapped[dict | None] = mapped_column(JSON)
    data_source: Mapped[str] = mapped_column(
        String(100), default="legacy_unspecified", server_default="legacy_unspecified"
    )
    is_synthetic: Mapped[bool | None] = mapped_column(Boolean)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=utc_now)


class RiskAssessment(Base):
    __tablename__ = "risk_assessments"
    __table_args__ = (
        CheckConstraint("risk_score >= 0 AND risk_score <= 1", name="score_range"),
        UniqueConstraint("assessment_id", "transaction_id", name="uq_assessments_transaction"),
    )
    assessment_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    transaction_id: Mapped[str] = mapped_column(
        ForeignKey("transactions.transaction_id"), index=True
    )
    risk_score: Mapped[Decimal] = mapped_column(Numeric(5, 4))
    reason_codes: Mapped[list[str]] = mapped_column(JSON)
    model_version: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    risk_category: Mapped[str | None] = mapped_column(String(16))
    method: Mapped[str] = mapped_column(String(32), default="legacy", server_default="legacy")
    status: Mapped[str] = mapped_column(String(32), default="legacy", server_default="legacy")
    factors: Mapped[list[dict]] = mapped_column(JSON, default=list, server_default="[]")
    missing_information: Mapped[list[str]] = mapped_column(JSON, default=list, server_default="[]")


class Evidence(Base):
    __tablename__ = "evidence"
    __table_args__ = (
        ForeignKeyConstraint(
            ["transaction_id", "case_id"],
            ["transactions.transaction_id", "transactions.case_id"],
        ),
        ForeignKeyConstraint(
            ["transaction_id"],
            ["transactions.transaction_id"],
            name="fk_evidence_source_transaction",
        ),
        ForeignKeyConstraint(
            ["assessment_id", "transaction_id"],
            ["risk_assessments.assessment_id", "risk_assessments.transaction_id"],
            name="fk_evidence_assessment_transaction",
        ),
        CheckConstraint("case_id IS NOT NULL OR assessment_id IS NOT NULL", name="association"),
    )
    evidence_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    case_id: Mapped[str | None] = mapped_column(ForeignKey("cases.case_id"), index=True)
    transaction_id: Mapped[str] = mapped_column(String(64))
    description: Mapped[str] = mapped_column(String(500))
    source: Mapped[str] = mapped_column(String(100))
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    assessment_id: Mapped[str | None] = mapped_column(String(64), index=True)
    account_id: Mapped[str | None] = mapped_column(ForeignKey("accounts.account_id"), index=True)
    kind: Mapped[str] = mapped_column(String(32), default="legacy", server_default="legacy")
    method: Mapped[str] = mapped_column(String(64), default="legacy", server_default="legacy")
    verification_status: Mapped[str] = mapped_column(
        String(24), default="unverified", server_default="unverified"
    )
    provenance: Mapped[dict] = mapped_column(JSON, default=dict, server_default="{}")


class AgentRequest(Base):
    __tablename__ = "agent_requests"
    request_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.case_id"), index=True)
    requested_by: Mapped[str] = mapped_column(ForeignKey("users.user_id"))
    agent_id: Mapped[str] = mapped_column(String(64))
    tool_name: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class PolicyDecision(Base):
    __tablename__ = "policy_decisions"
    __table_args__ = (
        CheckConstraint("decision IN ('ALLOW', 'DENY', 'REQUIRE_APPROVAL')", name="decision"),
    )
    decision_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    request_id: Mapped[str] = mapped_column(ForeignKey("agent_requests.request_id"), index=True)
    decision: Mapped[str] = mapped_column(String(32))
    reason: Mapped[str] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    event_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    case_id: Mapped[str | None] = mapped_column(ForeignKey("cases.case_id"), index=True)
    request_id: Mapped[str | None] = mapped_column(ForeignKey("agent_requests.request_id"))
    actor_id: Mapped[str] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(100))
    summary: Mapped[str] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
