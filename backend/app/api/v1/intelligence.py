"""Synthetic sandbox API. This is containment, not production authentication."""

from collections.abc import Generator
from datetime import UTC
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, inspect, select
from sqlalchemy.orm import Session

from app.core.auth import DEMO_USER_ID
from app.models import Account, Case, RiskAssessment, Transaction, User
from app.models.workflow import CaseEvent, CaseWorkflow, InvestigationReport, WorkflowBase
from app.repositories.intelligence import IntelligenceRepository
from app.schemas.intelligence import (
    AccountCreate,
    AccountRead,
    AssessmentRead,
    EvidenceCreate,
    EvidenceRead,
    Identifier,
    TransactionCreate,
    TransactionQuery,
    TransactionRead,
)
from app.schemas.workflow import (
    AnalysisRead,
    CaseLinks,
    CasePatch,
    DashboardRead,
    EventRead,
    GraphQuery,
    InvestigationCreate,
    InvestigationRead,
    NoteCreate,
    Page,
    ReportRead,
    ReportSummary,
    TransactionDetail,
    WorkflowStatus,
)
from app.services.detection import DetectionService
from app.services.evidence import EvidenceService
from app.services.investigations import InvestigationService
from app.services.relationships import RelationshipService

router = APIRouter(prefix="/intelligence", tags=["synthetic investigation sandbox"])


def sandbox_boundary(request: Request):
    settings = request.app.state.settings
    if (
        not settings.investigation_sandbox
        or not settings.demo_mode
        or settings.app_env == "production"
    ):
        raise HTTPException(
            403, "Investigation sandbox is disabled; the active database is protected"
        )
    if request.client is None or request.client.host not in {"127.0.0.1", "::1", "testclient"}:
        raise HTTPException(403, "Local synthetic sandbox access only")
    host = request.url.hostname
    if host not in {"localhost", "127.0.0.1", "::1", "testserver"}:
        raise HTTPException(403, "Invalid sandbox host")
    if request.method not in {"GET", "HEAD"}:
        if request.headers.get("x-fraudsentinel-sandbox") != "synthetic-only":
            raise HTTPException(403, "Explicit synthetic sandbox request required")
        origin = request.headers.get("origin")
        if origin and origin not in settings.cors_origins:
            raise HTTPException(403, "Request origin is not permitted")
        if request.headers.get("sec-fetch-site") == "cross-site":
            raise HTTPException(403, "Cross-site mutations are refused")
    return settings


def repository(
    request: Request, _: Annotated[object, Depends(sandbox_boundary)]
) -> Generator[IntelligenceRepository, None, None]:
    with Session(request.app.state.engine) as session, session.begin():
        user = session.get(User, DEMO_USER_ID)
        if user is None or user.role != "investigator":
            raise HTTPException(403, "Stored demo investigator access is required")
        yield IntelligenceRepository(session, DEMO_USER_ID)


Repo = Annotated[IntelligenceRepository, Depends(repository)]


@router.get("/capabilities")
def capabilities(request: Request):
    enabled = request.app.state.settings.investigation_sandbox
    return {
        "enabled": enabled,
        "mode": "synthetic_sandbox" if enabled else "protected_development",
        "required_revision": "0003_investigation_workflow",
        "message": "Synthetic isolated database; no production authentication."
        if enabled
        else (
            "Milestones 2–4 are available in the isolated sandbox. "
            "Active-database migration requires approval."
        ),
    }


@router.get("/dashboard", response_model=DashboardRead)
def dashboard(repo: Repo):
    scoped = repo._transactions().with_only_columns(Transaction.transaction_id).subquery()
    latest = (
        select(
            RiskAssessment.transaction_id,
            RiskAssessment.risk_category,
            func.row_number()
            .over(
                partition_by=RiskAssessment.transaction_id,
                order_by=(RiskAssessment.created_at.desc(), RiskAssessment.assessment_id.desc()),
            )
            .label("rank"),
        )
        .where(RiskAssessment.transaction_id.in_(select(scoped)))
        .subquery()
    )
    counts = dict(
        repo.session.execute(
            select(latest.c.risk_category, func.count())
            .where(latest.c.rank == 1)
            .group_by(latest.c.risk_category)
        ).all()
    )
    distribution = {key: counts.get(key, 0) for key in ("low", "medium", "high", "critical")}
    active = (
        repo.session.scalar(
            select(func.count())
            .select_from(Case)
            .outerjoin(CaseWorkflow)
            .where(Case.owner_id == repo.actor_id, Case.status != "closed")
        )
        or 0
    )
    recent_ids = repo.session.scalars(
        select(latest.c.transaction_id)
        .join(Transaction, Transaction.transaction_id == latest.c.transaction_id)
        .where(latest.c.rank == 1, latest.c.risk_category.in_(["high", "critical"]))
        .order_by(Transaction.occurred_at.desc(), latest.c.transaction_id)
        .limit(10)
    )
    events = repo.session.scalars(
        select(CaseEvent)
        .join(Case)
        .where(Case.owner_id == repo.actor_id)
        .order_by(CaseEvent.created_at.desc(), CaseEvent.event_id)
        .limit(10)
    )
    return {
        "transaction_count": repo.session.scalar(select(func.count()).select_from(scoped)) or 0,
        "suspicious_count": distribution["high"] + distribution["critical"],
        "risk_distribution": distribution,
        "open_investigations": active,
        "recent_high_risk": [repo.get_transaction(i).model_dump(mode="json") for i in recent_ids],
        "recent_activity": [InvestigationService(repo)._event_read(e) for e in events],
    }


@router.get("/transactions", response_model=list[TransactionRead])
def transactions(repo: Repo, query: Annotated[TransactionQuery, Query()]):
    return repo.list_transactions(query)


@router.post("/transactions", status_code=201, response_model=TransactionRead)
def ingest(data: TransactionCreate, repo: Repo):
    if not data.is_synthetic:
        raise HTTPException(422, "Sandbox accepts clearly labeled synthetic records only")
    if (
        not repo._account(data.source_account_id).is_synthetic
        or not repo._account(data.destination_account_id).is_synthetic
    ):
        raise HTTPException(422, "Sandbox account references must be synthetic")
    return repo.create_transaction(data)


@router.get("/transactions/{transaction_id}", response_model=TransactionDetail)
def transaction(transaction_id: Identifier, repo: Repo):
    return {
        "transaction": repo.get_transaction(transaction_id),
        "assessments": repo.list_assessments(transaction_id),
        "evidence": EvidenceService(repo).list(Page(limit=100), transaction_id=transaction_id),
    }


@router.post("/transactions/{transaction_id}/analyze", response_model=AnalysisRead)
def analyze(transaction_id: Identifier, request: Request, repo: Repo):
    result = DetectionService(repo, request.app.state.scoring_rules).analyze(transaction_id)
    tx = repo._transaction(transaction_id)
    if tx.case_id:
        InvestigationService(repo)._unique_link_event(
            tx.case_id,
            "assessment_recorded",
            "assessment_id",
            result["assessment"]["assessment_id"],
        )
    return result


@router.get("/assessments/{assessment_id}", response_model=AnalysisRead)
def assessment(assessment_id: Identifier, repo: Repo):
    return DetectionService(repo).get(assessment_id)


@router.get("/transactions/{transaction_id}/assessments", response_model=list[AssessmentRead])
def assessment_history(transaction_id: Identifier, repo: Repo, page: Annotated[Page, Query()]):
    repo._transaction(transaction_id)
    rows = repo.session.scalars(
        select(RiskAssessment)
        .where(RiskAssessment.transaction_id == transaction_id)
        .order_by(RiskAssessment.created_at.desc(), RiskAssessment.assessment_id)
        .limit(page.limit)
        .offset(page.offset)
    )
    return [repo._read_assessment(row) for row in rows]


@router.post("/assessments/{assessment_id}/evidence", response_model=list[EvidenceRead])
def collect(assessment_id: Identifier, repo: Repo):
    return EvidenceService(repo).collect(assessment_id)


@router.get("/accounts", response_model=list[AccountRead])
def accounts(repo: Repo, page: Annotated[Page, Query()]):
    from app.repositories.intelligence import read_contract
    from app.schemas.intelligence import AccountRead

    rows = repo.session.scalars(
        select(Account)
        .where(Account.owner_id == repo.actor_id)
        .order_by(Account.account_id)
        .limit(page.limit)
        .offset(page.offset)
    )
    return [read_contract(AccountRead, row) for row in rows]


@router.post("/accounts", status_code=201, response_model=AccountRead)
def account_create(data: AccountCreate, repo: Repo):
    if not data.is_synthetic:
        raise HTTPException(422, "Sandbox accepts synthetic account references only")
    return repo.create_account(data)


@router.get("/accounts/{account_id}/relationships")
def graph(account_id: Identifier, repo: Repo, query: Annotated[GraphQuery, Query()]):
    return RelationshipService(repo).graph(account_id, query)


@router.get("/evidence", response_model=list[EvidenceRead])
def evidence_list(
    repo: Repo,
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0, le=10000),
    case_id: Identifier | None = None,
    transaction_id: Identifier | None = None,
    account_id: Identifier | None = None,
    kind: Literal["observed_fact", "derived_indicator", "ai_interpretation", "legacy"]
    | None = None,
):
    return EvidenceService(repo).list(
        Page(limit=limit, offset=offset), case_id, transaction_id, account_id, kind
    )


@router.post("/evidence", status_code=201, response_model=EvidenceRead)
def evidence_create(data: EvidenceCreate, repo: Repo):
    result = EvidenceService(repo).create(data)
    if data.case_id:
        InvestigationService(repo)._unique_link_event(
            data.case_id, "evidence_linked", "evidence_id", result.evidence_id
        )
    return result


@router.get("/evidence/{evidence_id}", response_model=EvidenceRead)
def evidence_get(evidence_id: Identifier, repo: Repo):
    return repo.get_evidence(evidence_id)


@router.get("/cases", response_model=list[InvestigationRead])
def cases(
    repo: Repo,
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0, le=10000),
    status: WorkflowStatus | None = None,
):
    return InvestigationService(repo).list(Page(limit=limit, offset=offset), status)


@router.post("/cases", status_code=201, response_model=InvestigationRead)
def case_create(data: InvestigationCreate, repo: Repo):
    return InvestigationService(repo).create(data)


@router.get("/cases/{case_id}", response_model=InvestigationRead)
def case_detail(case_id: Identifier, repo: Repo):
    return InvestigationService(repo).get(case_id)


@router.get("/cases/{case_id}/transactions", response_model=list[TransactionRead])
def case_transactions(case_id: Identifier, repo: Repo, page: Annotated[Page, Query()]):
    from app.repositories.intelligence import read_contract

    repo._case(case_id)
    rows = repo.session.scalars(
        repo._transactions()
        .where(Transaction.case_id == case_id)
        .order_by(Transaction.occurred_at.desc(), Transaction.transaction_id)
        .limit(page.limit)
        .offset(page.offset)
    )
    return [read_contract(TransactionRead, row) for row in rows]


@router.patch("/cases/{case_id}", response_model=InvestigationRead)
def case_update(case_id: Identifier, data: CasePatch, repo: Repo):
    return InvestigationService(repo).update(case_id, data)


@router.post("/cases/{case_id}/links", response_model=InvestigationRead)
def case_links(case_id: Identifier, data: CaseLinks, repo: Repo):
    return InvestigationService(repo).link(case_id, data)


@router.post("/cases/{case_id}/notes", status_code=201, response_model=EventRead)
def case_note(case_id: Identifier, data: NoteCreate, repo: Repo):
    return InvestigationService(repo).note(case_id, data.text)


@router.get("/cases/{case_id}/timeline", response_model=list[EventRead])
def timeline(case_id: Identifier, repo: Repo, page: Annotated[Page, Query()]):
    return InvestigationService(repo).timeline(case_id, page)


@router.post("/cases/{case_id}/reports", response_model=ReportRead)
def generate_report(case_id: Identifier, repo: Repo):
    return InvestigationService(repo).report(case_id)


@router.get("/cases/{case_id}/reports", response_model=list[ReportSummary])
def reports(case_id: Identifier, repo: Repo, page: Annotated[Page, Query()]):
    repo._case(case_id)
    return [
        {
            "report_id": row.report_id,
            "created_at": row.created_at.replace(tzinfo=row.created_at.tzinfo or UTC),
            "fingerprint": row.fingerprint,
        }
        for row in repo.session.scalars(
            select(InvestigationReport)
            .where(InvestigationReport.case_id == case_id)
            .order_by(InvestigationReport.created_at.desc(), InvestigationReport.report_id)
            .limit(page.limit)
            .offset(page.offset)
        )
    ]


@router.get("/cases/{case_id}/reports/{report_id}", response_model=ReportRead)
def get_report(case_id: Identifier, report_id: Identifier, repo: Repo):
    return InvestigationService(repo).get_report(case_id, report_id)


def validate_sandbox_engine(config, engine):
    if not config.investigation_sandbox:
        return
    database = engine.url.database or ""
    memory_fixture = (
        config.app_env == "test"
        and engine.dialect.name == "sqlite"
        and database in {"", ":memory:"}
    )
    isolated_postgres = (
        engine.dialect.name == "postgresql"
        and database.startswith("fraudsentinel_sandbox_")
        and engine.url.host in {"127.0.0.1", "localhost", "::1"}
    )
    if not (memory_fixture or isolated_postgres):
        raise ValueError(
            "Sandbox API requires an isolated synthetic database; "
            "active development database refused"
        )
    with engine.connect() as connection:
        if not set(WorkflowBase.metadata.tables).issubset(inspect(connection).get_table_names()):
            raise ValueError("Sandbox schema requires reviewed migration 0003")
