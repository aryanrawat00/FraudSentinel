"""Scoped persistence primitives; the caller owns the transaction/commit.

actor_id must come from a trusted service identity, never from an HTTP body/header.
HTTP writes are contained in the explicitly enabled isolated synthetic sandbox.
Real-data mutation APIs require the later authentication and policy milestone.
"""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import and_, inspect, or_, select
from sqlalchemy.orm import Session

from app.models import (
    Account,
    AuditEvent,
    Case,
    CaseAccount,
    Evidence,
    RiskAssessment,
    Transaction,
    User,
)
from app.schemas.intelligence import (
    AccountCreate,
    AccountRead,
    AssessmentCreate,
    AssessmentRead,
    CaseCreate,
    CaseRead,
    EvidenceCreate,
    EvidenceRead,
    TransactionCreate,
    TransactionQuery,
    TransactionRead,
)


class AccessDenied(ValueError):
    pass


class ResourceNotFound(ValueError):
    pass


class Conflict(ValueError):
    pass


def read_contract(contract, row, **overrides):
    values = {name: getattr(row, name) for name in contract.model_fields if name not in overrides}
    values.update(overrides)
    # PostgreSQL preserves offsets; SQLite fixtures round-trip UTC as naive values.
    values = {
        name: value.replace(tzinfo=UTC)
        if isinstance(value, datetime) and value.tzinfo is None
        else value
        for name, value in values.items()
    }
    return contract.model_validate(values)


class IntelligenceRepository:
    def __init__(self, session: Session, actor_id: str):
        self.session = session
        self.actor_id = actor_id
        user = session.get(User, actor_id)
        if user is None or user.role not in {
            "administrator",
            "analyst",
            "investigator",
            "reviewer",
        }:
            raise AccessDenied("An authorized application principal is required")
        self.role = user.role

    def _write(self):
        if self.role == "reviewer":
            raise AccessDenied("Read-only principals cannot modify investigation data")

    def _new_id(self, model, identifier):
        key = inspect(model).primary_key[0]
        if self.session.scalar(select(key).where(key == identifier)) is not None:
            raise Conflict("Identifier is unavailable; existing records are never overwritten")

    def _audit(self, action, case_id=None):
        self.session.add(
            AuditEvent(
                event_id=f"event_{uuid4().hex}",
                case_id=case_id,
                actor_id=self.actor_id,
                action=action,
                summary=action.replace("_", " ").capitalize(),
            )
        )

    def _account(self, account_id):
        row = self.session.scalar(
            select(Account).where(
                Account.account_id == account_id, Account.owner_id == self.actor_id
            )
        )
        if row is None:
            raise ResourceNotFound("Account not found in the authorized scope")
        return row

    def _case(self, case_id):
        row = self.session.scalar(
            select(Case).where(Case.case_id == case_id, Case.owner_id == self.actor_id)
        )
        if row is None:
            raise ResourceNotFound("Case not found in the authorized scope")
        return row

    def _scope(self):
        return or_(
            Transaction.owner_id == self.actor_id,
            and_(Transaction.owner_id.is_(None), Case.owner_id == self.actor_id),
        )

    def _transactions(self):
        return (
            select(Transaction)
            .outerjoin(Case, Transaction.case_id == Case.case_id)
            .where(self._scope())
        )

    def _validate_sources(self, identifiers):
        expected = set(identifiers)
        if len(expected) > 100:
            raise ValueError("At most 100 distinct supporting transactions are permitted")
        if not expected:
            return
        found = set(
            self.session.scalars(
                self._transactions()
                .with_only_columns(Transaction.transaction_id)
                .where(Transaction.transaction_id.in_(expected))
            )
        )
        if found != expected:
            raise ResourceNotFound("Supporting transactions not found in the authorized scope")

    def _transaction(self, transaction_id):
        row = self.session.scalar(
            self._transactions().where(Transaction.transaction_id == transaction_id)
        )
        if row is None:
            raise ResourceNotFound("Transaction not found in the authorized scope")
        return row

    def _assessment(self, assessment_id):
        row = self.session.scalar(
            select(RiskAssessment)
            .join(Transaction, RiskAssessment.transaction_id == Transaction.transaction_id)
            .outerjoin(Case, Transaction.case_id == Case.case_id)
            .where(RiskAssessment.assessment_id == assessment_id, self._scope())
        )
        if row is None:
            raise ResourceNotFound("Assessment not found in the authorized scope")
        return row

    def create_account(self, data: AccountCreate) -> AccountRead:
        self._write()
        self._new_id(Account, data.account_id)
        row = Account(**data.model_dump(), owner_id=self.actor_id)
        self.session.add(row)
        self._audit("ACCOUNT_REFERENCE_CREATED")
        self.session.flush()
        return read_contract(AccountRead, row)

    def get_account(self, account_id: str) -> AccountRead:
        return read_contract(AccountRead, self._account(account_id))

    def create_transaction(self, data: TransactionCreate) -> TransactionRead:
        self._write()
        self._account(data.source_account_id)
        self._account(data.destination_account_id)
        self._new_id(Transaction, data.transaction_id)
        values = data.model_dump(exclude={"location"})
        values["location"] = data.location.model_dump(mode="json") if data.location else None
        row = Transaction(**values, owner_id=self.actor_id, case_id=None)
        self.session.add(row)
        self._audit("TRANSACTION_INGESTED")
        self.session.flush()
        return read_contract(TransactionRead, row)

    def get_transaction(self, transaction_id: str) -> TransactionRead:
        return read_contract(TransactionRead, self._transaction(transaction_id))

    def list_transactions(self, query: TransactionQuery) -> list[TransactionRead]:
        statement = self._transactions()
        if query.account_id:
            self._account(query.account_id)
            statement = statement.where(
                or_(
                    Transaction.source_account_id == query.account_id,
                    Transaction.destination_account_id == query.account_id,
                )
            )
        if query.currency:
            statement = statement.where(Transaction.currency == query.currency)
        if query.occurred_from:
            statement = statement.where(Transaction.occurred_at >= query.occurred_from)
        if query.occurred_before:
            statement = statement.where(Transaction.occurred_at < query.occurred_before)
        rows = self.session.scalars(
            statement.order_by(Transaction.occurred_at.desc(), Transaction.transaction_id)
            .limit(query.limit)
            .offset(query.offset)
        )
        return [read_contract(TransactionRead, row) for row in rows]

    def create_case(self, data: CaseCreate) -> CaseRead:
        self._write()
        self._new_id(Case, data.case_id)
        row = Case(**data.model_dump(), owner_id=self.actor_id, updated_at=datetime.now(UTC))
        self.session.add(row)
        self.session.flush()
        self._audit("CASE_CREATED", row.case_id)
        return read_contract(CaseRead, row)

    def get_case(self, case_id: str) -> CaseRead:
        return read_contract(CaseRead, self._case(case_id))

    def attach_transaction(self, case_id: str, transaction_id: str) -> TransactionRead:
        self._write()
        case = self._case(case_id)
        self.session.execute(select(Case.case_id).where(Case.case_id == case_id).with_for_update())
        transaction = self.session.scalar(
            self._transactions()
            .where(Transaction.transaction_id == transaction_id)
            .with_for_update(of=Transaction)
            .execution_options(populate_existing=True)
        )
        if transaction is None:
            raise ResourceNotFound("Transaction not found in the authorized scope")
        if transaction.case_id not in (None, case_id):
            raise Conflict(
                "Moving a transaction could invalidate evidence; reassignment is refused"
            )
        if transaction.case_id is None:
            transaction.case_id = case_id
            case.updated_at = datetime.now(UTC)
            self._audit("TRANSACTION_ATTACHED", case_id)
            self.session.flush()
        return read_contract(TransactionRead, transaction)

    def attach_account(self, case_id: str, account_id: str) -> None:
        self._write()
        case = self._case(case_id)
        self.session.execute(select(Case.case_id).where(Case.case_id == case_id).with_for_update())
        self._account(account_id)
        if self.session.get(CaseAccount, (case_id, account_id)) is None:
            self.session.add(
                CaseAccount(case_id=case_id, account_id=account_id, owner_id=self.actor_id)
            )
            case.updated_at = datetime.now(UTC)
            self._audit("ACCOUNT_ATTACHED", case_id)
            self.session.flush()

    def record_assessment(self, data: AssessmentCreate) -> AssessmentRead:
        self._write()
        transaction = self._transaction(data.transaction_id)
        self._validate_sources(
            {item for factor in data.factors for item in factor.source_transaction_ids}
        )
        self._new_id(RiskAssessment, data.assessment_id)
        row = RiskAssessment(
            assessment_id=data.assessment_id,
            transaction_id=data.transaction_id,
            risk_score=(data.score / 100).quantize(Decimal("0.0001")),
            risk_category=data.risk_category,
            method=data.method,
            status=data.status,
            reason_codes=[factor.code for factor in data.factors],
            model_version=data.ruleset_version,
            factors=[factor.model_dump(mode="json") for factor in data.factors],
            missing_information=data.missing_information,
        )
        self.session.add(row)
        self._audit("ASSESSMENT_RECORDED", transaction.case_id)
        self.session.flush()
        return self._read_assessment(row)

    def _read_assessment(self, row):
        return read_contract(
            AssessmentRead,
            row,
            score=(row.risk_score * 100).quantize(Decimal("0.01")),
            ruleset_version=row.model_version,
        )

    def list_assessments(self, transaction_id: str, limit: int = 25) -> list[AssessmentRead]:
        self._transaction(transaction_id)
        if not 1 <= limit <= 100:
            raise ValueError("Limit must be between 1 and 100")
        rows = self.session.scalars(
            select(RiskAssessment)
            .where(RiskAssessment.transaction_id == transaction_id)
            .order_by(RiskAssessment.created_at.desc(), RiskAssessment.assessment_id)
            .limit(limit)
        )
        return [self._read_assessment(row) for row in rows]

    def create_evidence(self, data: EvidenceCreate) -> EvidenceRead:
        self._write()
        transaction = self._transaction(data.transaction_id)
        if data.case_id:
            self._case(data.case_id)
            if transaction.case_id != data.case_id:
                raise Conflict("Evidence must remain within its transaction's case")
        if data.assessment_id:
            assessment = self._assessment(data.assessment_id)
            if assessment.transaction_id != data.transaction_id:
                raise Conflict("Evidence must reference the assessed transaction")
        if data.account_id:
            self._account(data.account_id)
            if data.account_id not in (
                transaction.source_account_id,
                transaction.destination_account_id,
            ):
                raise Conflict("Evidence account must be an observed transaction participant")
        self._validate_sources(data.provenance.source_transaction_ids)
        self._new_id(Evidence, data.evidence_id)
        row = Evidence(
            **data.model_dump(exclude={"provenance"}),
            provenance=data.provenance.model_dump(mode="json"),
        )
        self.session.add(row)
        self._audit("EVIDENCE_RECORDED", data.case_id)
        self.session.flush()
        return read_contract(EvidenceRead, row)

    def get_evidence(self, evidence_id: str) -> EvidenceRead:
        row = self.session.scalar(
            select(Evidence)
            .join(Transaction, Evidence.transaction_id == Transaction.transaction_id)
            .outerjoin(Case, Transaction.case_id == Case.case_id)
            .where(Evidence.evidence_id == evidence_id, self._scope())
        )
        if row is None:
            raise ResourceNotFound("Evidence not found in the authorized scope")
        return read_contract(EvidenceRead, row, provenance=row.provenance or None)
