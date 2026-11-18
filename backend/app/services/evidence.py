from datetime import UTC

from sqlalchemy import select

from app.models import Case, Evidence, Transaction
from app.models.workflow import EvidenceFingerprint
from app.repositories.intelligence import Conflict
from app.schemas.intelligence import EvidenceCreate
from app.schemas.workflow import Page
from app.services.access import lock_mutable_transaction
from app.services.detection import fingerprint


class EvidenceService:
    def __init__(self, repo):
        self.repo = repo

    def create(self, data: EvidenceCreate):
        self.repo._write()
        # Validate every requested source and case before considering deduplication.
        tx = lock_mutable_transaction(self.repo, data.transaction_id)
        self.repo._validate_sources(data.provenance.source_transaction_ids)
        if data.case_id:
            if self.repo._case(data.case_id).status == "closed":
                raise Conflict("Closed cases are read-only")
            if tx.case_id != data.case_id:
                raise Conflict("Evidence and transaction must belong to the same case")
        if data.assessment_id:
            if self.repo._assessment(data.assessment_id).transaction_id != data.transaction_id:
                raise Conflict("Evidence must reference its source assessment")
        if data.account_id:
            self.repo._account(data.account_id)
            if data.account_id not in (tx.source_account_id, tx.destination_account_id):
                raise Conflict("Evidence account is not a transaction participant")
        # Evidence supports this case only, never another case's sources.
        if data.case_id:
            sources = self.repo.session.scalars(
                self.repo._transactions().where(
                    Transaction.transaction_id.in_(data.provenance.source_transaction_ids)
                )
            )
            if any(row.case_id not in (None, data.case_id) for row in sources):
                raise Conflict("Evidence sources cannot cross investigation cases")
        canonical = data.model_dump(mode="json", exclude={"evidence_id"})
        canonical["provenance"]["source_transaction_ids"] = sorted(
            set(data.provenance.source_transaction_ids)
        )
        digest = fingerprint({"actor": self.repo.actor_id, "evidence": canonical})
        existing = self.repo.session.scalar(
            select(EvidenceFingerprint).where(EvidenceFingerprint.fingerprint == digest)
        )
        if existing:
            return self.repo.get_evidence(existing.evidence_id)
        saved = self.repo.create_evidence(data)
        self.repo.session.add(
            EvidenceFingerprint(evidence_id=saved.evidence_id, fingerprint=digest)
        )
        self.repo.session.flush()
        return saved

    def collect(self, assessment_id):
        self.repo._write()
        assessment = self.repo._assessment(assessment_id)
        transaction = self.repo._transaction(assessment.transaction_id)
        if transaction.case_id and self.repo._case(transaction.case_id).status == "closed":
            raise Conflict("Closed cases are read-only")
        result = []
        for factor in assessment.factors:
            identifier = (
                "evi_" + fingerprint({"assessment": assessment_id, "code": factor["code"]})[:48]
            )
            if self.repo.session.get(Evidence, identifier):
                result.append(self.repo.get_evidence(identifier))
                continue
            result.append(
                self.create(
                    EvidenceCreate(
                        evidence_id=identifier,
                        transaction_id=transaction.transaction_id,
                        assessment_id=assessment_id,
                        account_id=transaction.source_account_id,
                        description=factor["description"],
                        source="deterministic_detection",
                        kind="derived_indicator",
                        method=assessment.model_version,
                        provenance={
                            "source_reference": (
                                f"assessment:{assessment_id}/factor:{factor['code']}"
                            ),
                            "source_transaction_ids": factor["source_transaction_ids"],
                            "observed_at": assessment.created_at.replace(
                                tzinfo=assessment.created_at.tzinfo or UTC
                            ),
                        },
                    )
                )
            )
        return result

    def list(self, page: Page, case_id=None, transaction_id=None, account_id=None, kind=None):
        statement = (
            select(Evidence)
            .join(Transaction, Evidence.transaction_id == Transaction.transaction_id)
            .outerjoin(Case, Case.case_id == Transaction.case_id)
            .where(self.repo._scope())
        )
        if case_id:
            self.repo._case(case_id)
            statement = statement.where(Evidence.case_id == case_id)
        if transaction_id:
            self.repo._transaction(transaction_id)
            statement = statement.where(Evidence.transaction_id == transaction_id)
        if account_id:
            self.repo._account(account_id)
            statement = statement.where(Evidence.account_id == account_id)
        if kind:
            statement = statement.where(Evidence.kind == kind)
        rows = self.repo.session.scalars(
            statement.order_by(Evidence.captured_at.desc(), Evidence.evidence_id)
            .limit(page.limit)
            .offset(page.offset)
        )
        from app.repositories.intelligence import read_contract
        from app.schemas.intelligence import EvidenceRead

        return [read_contract(EvidenceRead, row, provenance=row.provenance or None) for row in rows]
