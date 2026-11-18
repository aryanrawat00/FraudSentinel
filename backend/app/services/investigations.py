"""Case workflow with append-only events and immutable, source-backed reports."""

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select

from app.models import Account, Case, CaseAccount, Evidence, RiskAssessment, Transaction
from app.models.workflow import CaseEvent, CaseWorkflow, InvestigationReport
from app.repositories.intelligence import AccessDenied, Conflict, ResourceNotFound, read_contract
from app.schemas.intelligence import AccountRead, CaseCreate, EvidenceRead, TransactionRead
from app.schemas.workflow import CaseLinks, CasePatch, InvestigationCreate, Page
from app.services.detection import fingerprint
from app.services.relationships import RelationshipService

TRANSITIONS = {
    "open": {"under_investigation", "closed"},
    "under_investigation": {"pending_review"},
    "pending_review": {"under_investigation", "resolved"},
    "resolved": {"under_investigation", "closed"},
    "closed": set(),
}
LEGACY_STATUS = {"open": "open", "in_review": "under_investigation", "closed": "closed"}


class InvestigationService:
    def __init__(self, repo):
        self.repo = repo
        self.session = repo.session

    def _locked(self, case_id):
        self.repo._write()
        row = self.session.scalar(
            select(Case)
            .where(Case.case_id == case_id, Case.owner_id == self.repo.actor_id)
            .with_for_update()
        )
        if row is None:
            raise ResourceNotFound("Case not found in the authorized scope")
        workflow = self.session.get(CaseWorkflow, case_id, populate_existing=True)
        if workflow is None:
            workflow = CaseWorkflow(
                case_id=case_id,
                owner_id=self.repo.actor_id,
                status=LEGACY_STATUS[row.status],
                version=1,
            )
            self.session.add(workflow)
            self.session.flush()
        return row, workflow

    def event(self, case_id, kind, description, references=None):
        self.repo._write()
        self.repo._case(case_id)
        event = CaseEvent(
            event_id=f"evt_{uuid4().hex}",
            case_id=case_id,
            actor_id=self.repo.actor_id,
            kind=kind,
            description=description,
            references=references or {},
        )
        self.session.add(event)
        self.session.flush()
        return self._event_read(event)

    def _event_read(self, event):
        return {
            "event_id": event.event_id,
            "case_id": event.case_id,
            "actor_id": event.actor_id,
            "kind": event.kind,
            "description": event.description,
            "references": event.references,
            "created_at": event.created_at.replace(
                tzinfo=event.created_at.tzinfo or UTC
            ).isoformat(),
        }

    def get(self, case_id):
        row = self.repo._case(case_id)
        workflow = self.session.get(CaseWorkflow, case_id)
        data = self.repo.get_case(case_id).model_dump(mode="json")
        data.update(
            {
                "legacy_status": row.status,
                "status": workflow.status if workflow else LEGACY_STATUS[row.status],
                "version": workflow.version if workflow else 1,
                "assigned_to": workflow.assigned_to if workflow else None,
            }
        )
        return data

    def list(self, page: Page, status=None):
        statement = (
            select(Case)
            .outerjoin(CaseWorkflow, Case.case_id == CaseWorkflow.case_id)
            .where(Case.owner_id == self.repo.actor_id)
        )
        if status:
            from sqlalchemy import and_, or_

            legacy = [key for key, value in LEGACY_STATUS.items() if value == status]
            statement = statement.where(
                or_(
                    CaseWorkflow.status == status,
                    and_(CaseWorkflow.case_id.is_(None), Case.status.in_(legacy)),
                )
            )
        rows = list(
            self.session.scalars(
                statement.order_by(Case.created_at.desc(), Case.case_id)
                .limit(page.limit)
                .offset(page.offset)
            )
        )
        workflows = {
            row.case_id: row
            for row in self.session.scalars(
                select(CaseWorkflow).where(CaseWorkflow.case_id.in_([r.case_id for r in rows]))
            )
        }
        result = []
        for row in rows:
            from app.schemas.intelligence import CaseRead

            item = read_contract(CaseRead, row).model_dump(mode="json")
            wf = workflows.get(row.case_id)
            item.update(
                legacy_status=row.status,
                status=wf.status if wf else LEGACY_STATUS[row.status],
                version=wf.version if wf else 1,
                assigned_to=wf.assigned_to if wf else None,
            )
            result.append(item)
        return result

    def create(self, data: InvestigationCreate):
        self.repo.create_case(
            CaseCreate.model_validate(
                data.model_dump(
                    exclude={"transaction_ids", "assessment_ids", "account_ids", "evidence_ids"}
                )
            )
        )
        self._locked(data.case_id)
        self.event(
            data.case_id, "case_created", "Investigation opened; no fraud conclusion recorded."
        )
        self.link(
            data.case_id,
            CaseLinks.model_validate(
                data.model_dump(
                    include={"transaction_ids", "assessment_ids", "account_ids", "evidence_ids"}
                )
            ),
        )
        return self.get(data.case_id)

    def update(self, case_id, data: CasePatch):
        row, workflow = self._locked(case_id)
        if workflow.version != data.expected_version:
            raise Conflict("Case changed since it was loaded; refresh before updating")
        if workflow.status == "closed":
            raise Conflict("Closed cases are read-only")
        if (
            data.status
            and data.status != workflow.status
            and data.status not in TRANSITIONS[workflow.status]
        ):
            raise Conflict("Invalid investigation status transition")
        if data.assigned_to and data.assigned_to != self.repo.actor_id:
            raise AccessDenied(
                "Cross-user assignment requires the later identity and policy milestone"
            )
        changes = {}
        for name in ("title", "description", "priority"):
            value = getattr(data, name)
            if value is not None and value != getattr(row, name):
                changes[name] = {"before": getattr(row, name), "after": value}
                setattr(row, name, value)
        if data.status and data.status != workflow.status:
            changes["status"] = {"before": workflow.status, "after": data.status}
            workflow.status = data.status
            row.status = (
                "closed"
                if data.status == "closed"
                else "open"
                if data.status == "open"
                else "in_review"
            )
        if "assigned_to" in data.model_fields_set and data.assigned_to != workflow.assigned_to:
            changes["assigned_to"] = {"before": workflow.assigned_to, "after": data.assigned_to}
            workflow.assigned_to = data.assigned_to
        if changes:
            row.updated_at = datetime.now(UTC)
            workflow.version += 1
            self.event(
                case_id, "case_updated", "Investigation information updated.", {"changes": changes}
            )
        return self.get(case_id)

    def link(self, case_id, data: CaseLinks):
        row, workflow = self._locked(case_id)
        changed = False
        if workflow.status == "closed":
            raise Conflict("Closed cases are read-only")
        tx_ids = set(data.transaction_ids)
        for identifier in data.assessment_ids:
            tx_ids.add(self.repo._assessment(identifier).transaction_id)
        for identifier in data.evidence_ids:
            tx_ids.add(self.repo.get_evidence(identifier).transaction_id)
        for identifier in sorted(tx_ids):
            tx = self.repo._transaction(identifier)
            before = tx.case_id
            self.repo.attach_transaction(case_id, identifier)
            if before is None:
                changed = True
                self.event(
                    case_id,
                    "transaction_linked",
                    "Stored transaction associated with the investigation.",
                    {"transaction_id": identifier},
                )
        for identifier in sorted(set(data.account_ids)):
            before = self.session.get(CaseAccount, (case_id, identifier))
            self.repo.attach_account(case_id, identifier)
            if before is None:
                changed = True
                self.event(
                    case_id,
                    "account_linked",
                    "Account reference associated; legal ownership is not inferred.",
                    {"account_id": identifier},
                )
        for identifier in sorted(set(data.assessment_ids)):
            changed |= self._unique_link_event(
                case_id, "assessment_linked", "assessment_id", identifier
            )
        for identifier in sorted(set(data.evidence_ids)):
            self.repo.get_evidence(identifier)
            evidence = self.session.get(Evidence, identifier)
            if evidence.case_id not in (None, case_id):
                raise Conflict("Evidence cannot be moved between cases")
            ids = (evidence.provenance or {}).get(
                "source_transaction_ids", [evidence.transaction_id]
            )
            self.repo._validate_sources(ids)
            sources = self.session.scalars(
                self.repo._transactions().where(Transaction.transaction_id.in_(ids))
            )
            if any(source.case_id not in (None, case_id) for source in sources):
                raise Conflict("Evidence provenance crosses another investigation")
            if evidence.case_id is None:
                evidence.case_id = case_id
                changed = True
            changed |= self._unique_link_event(
                case_id, "evidence_linked", "evidence_id", identifier
            )
        if changed:
            workflow.version += 1
            row.updated_at = datetime.now(UTC)
        self.session.flush()
        return self.get(case_id)

    def _unique_link_event(self, case_id, kind, key, identifier):
        event_id = "link_" + fingerprint([case_id, kind, identifier])[:48]
        if self.session.get(CaseEvent, event_id) is None:
            self.session.add(
                CaseEvent(
                    event_id=event_id,
                    case_id=case_id,
                    actor_id=self.repo.actor_id,
                    kind=kind,
                    description="Stored record linked to investigation.",
                    references={key: identifier},
                )
            )
            self.session.flush()
            return True
        return False

    def note(self, case_id, text):
        row, workflow = self._locked(case_id)
        if workflow.status == "closed":
            raise Conflict("Closed cases are read-only")
        workflow.version += 1
        row.updated_at = datetime.now(UTC)
        return self.event(case_id, "analyst_note", text)

    def timeline(self, case_id, page: Page):
        self.repo._case(case_id)
        rows = self.session.scalars(
            select(CaseEvent)
            .where(CaseEvent.case_id == case_id)
            .order_by(CaseEvent.created_at, CaseEvent.event_id)
            .limit(page.limit)
            .offset(page.offset)
        )
        return [self._event_read(row) for row in rows]

    def report(self, case_id):
        self._locked(case_id)
        case = self.get(case_id)
        txs = list(
            self.session.scalars(
                self.repo._transactions()
                .where(Transaction.case_id == case_id)
                .order_by(Transaction.transaction_id)
                .limit(101)
            )
        )
        if len(txs) > 100:
            raise Conflict(
                "Report limit is 100 case transactions; narrow the investigation before export"
            )
        assessments = list(
            self.session.scalars(
                select(RiskAssessment)
                .where(RiskAssessment.transaction_id.in_([r.transaction_id for r in txs]))
                .order_by(RiskAssessment.created_at, RiskAssessment.assessment_id)
                .limit(501)
            )
        )
        events = list(
            self.session.scalars(
                select(CaseEvent)
                .where(CaseEvent.case_id == case_id, CaseEvent.kind != "report_generated")
                .order_by(CaseEvent.created_at, CaseEvent.event_id)
                .limit(501)
            )
        )
        evidence_rows = list(
            self.session.scalars(
                select(Evidence)
                .where(Evidence.case_id == case_id)
                .order_by(Evidence.evidence_id)
                .limit(101)
            )
        )
        if len(events) > 500 or len(assessments) > 500 or len(evidence_rows) > 100:
            raise Conflict(
                "Report exceeds bounded history/evidence limits; no partial report was generated"
            )
        account_ids = set(
            self.session.scalars(
                select(CaseAccount.account_id).where(CaseAccount.case_id == case_id)
            )
        )
        account_ids.update(
            a for tx in txs for a in (tx.source_account_id, tx.destination_account_id) if a
        )
        if len(account_ids) > 100:
            raise Conflict("Report exceeds 100 related accounts")
        accounts = self.session.scalars(
            select(Account)
            .where(Account.account_id.in_(account_ids), Account.owner_id == self.repo.actor_id)
            .order_by(Account.account_id)
        )
        graph = RelationshipService.from_records(None, txs)
        relationships = graph["findings"]
        source_ids = {
            identifier
            for item in evidence_rows
            for identifier in (item.provenance or {}).get(
                "source_transaction_ids", [item.transaction_id]
            )
        }
        source_ids.update(
            identifier
            for assessment in assessments
            for factor in assessment.factors
            for identifier in factor["source_transaction_ids"]
        )
        if len(source_ids) > 500:
            raise Conflict("Report exceeds 500 supporting evidence source records")
        sources = list(
            self.session.scalars(
                self.repo._transactions()
                .where(Transaction.transaction_id.in_(source_ids))
                .order_by(Transaction.transaction_id)
            )
        )
        if {row.transaction_id for row in sources} != source_ids:
            raise Conflict("Report evidence contains unavailable source references")
        if any(row.case_id not in (None, case_id) for row in sources):
            raise Conflict("Report evidence provenance crosses another investigation")
        evidence = [
            read_contract(EvidenceRead, row, provenance=row.provenance or None).model_dump(
                mode="json"
            )
            for row in evidence_rows
        ]
        timeline = [self._event_read(e) for e in events]
        content = {
            "report_version": "investigation_v1",
            "case": case,
            "recorded_facts": {
                "accounts": [
                    read_contract(AccountRead, a).model_dump(mode="json") for a in accounts
                ],
                "transactions": [
                    read_contract(TransactionRead, tx).model_dump(mode="json") for tx in txs
                ],
            },
            "system_findings": {
                "assessments": [
                    self.repo._read_assessment(a).model_dump(mode="json") for a in assessments
                ],
                "relationships": relationships,
                "relationship_analysis_bounds": {
                    "finding_limit": 100,
                    "truncated": graph["truncated"],
                },
            },
            "evidence": evidence,
            "verified_facts": [e for e in evidence if e["verification_status"] == "verified"],
            "supporting_source_transactions": [
                read_contract(TransactionRead, tx).model_dump(mode="json") for tx in sources
            ],
            "timeline": timeline,
            "analyst_notes": [e for e in timeline if e["kind"] == "analyst_note"],
            "observations": [
                f"{len(txs)} stored case transactions and "
                f"{len(assessments)} historical assessments included.",
                "Evidence verification labels are preserved; "
                "a stored record is not independently verified truth.",
            ],
            "recommendations": [
                "Review each contributing factor against its source transactions.",
                "Obtain missing context through authorized channels "
                "and record analyst conclusions.",
                "Seek human review before financial or account actions.",
            ],
            "limitations": [
                "Rule scores are review indicators, not fraud probability or confirmation.",
                "Relationship findings are bounded, case-source-only observations, "
                "not a complete network.",
                "Historical legacy events may predate the detailed timeline.",
                "No independent verification workflow is implemented in this milestone.",
                "Account dataset scope does not establish legal ownership.",
                *sorted({m for a in assessments for m in a.missing_information}),
            ],
        }
        digest = fingerprint(content)
        identifier = "report_" + digest[:48]
        existing = self.session.get(InvestigationReport, identifier)
        if existing is None:
            existing = InvestigationReport(
                report_id=identifier, case_id=case_id, fingerprint=digest, content=content
            )
            self.session.add(existing)
            self.session.flush()
            self.event(
                case_id,
                "report_generated",
                "Immutable JSON investigation report generated.",
                {"report_id": identifier, "sha256": digest},
            )
        return self.get_report(case_id, identifier)

    def get_report(self, case_id, report_id):
        self.repo._case(case_id)
        row = self.session.scalar(
            select(InvestigationReport).where(
                InvestigationReport.case_id == case_id, InvestigationReport.report_id == report_id
            )
        )
        if row is None:
            raise ResourceNotFound("Report not found in the authorized case")
        return {
            "report_id": row.report_id,
            "case_id": case_id,
            "fingerprint": row.fingerprint,
            "created_at": row.created_at.replace(tzinfo=row.created_at.tzinfo or UTC).isoformat(),
            "content": row.content,
        }
