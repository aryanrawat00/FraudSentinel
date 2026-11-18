"""Isolated fixtures exercise real repositories, HTTP boundaries and the full workflow."""

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.main import create_app
from app.models import Case, RiskAssessment, User
from app.models.workflow import AnalysisRun, WorkflowBase
from app.repositories.intelligence import (
    AccessDenied,
    Conflict,
    IntelligenceRepository,
    ResourceNotFound,
)
from app.schemas.intelligence import TransactionCreate
from app.schemas.workflow import CaseLinks, CasePatch, GraphQuery, InvestigationCreate, Page
from app.services.detection import DetectionService, Rules, evaluate, fingerprint
from app.services.evidence import EvidenceService
from app.services.investigations import InvestigationService
from app.services.relationships import RelationshipService
from scripts.seed_demo_data import seed_demo
from scripts.synthetic_scenarios import create_scenarios


@pytest.fixture
def workflow_engine(engine):
    WorkflowBase.metadata.create_all(engine)
    with Session(engine) as session, session.begin():
        seed_demo(session)
        create_scenarios(IntelligenceRepository(session, "user_demo_analyst"))
    return engine


@pytest.fixture
def repo(workflow_engine):
    with Session(workflow_engine) as session, session.begin():
        yield IntelligenceRepository(session, "user_demo_analyst")


@pytest.fixture
def sandbox(workflow_engine):
    settings = Settings(_env_file=None, app_env="test", demo_mode=True, investigation_sandbox=True)
    with TestClient(
        create_app(settings, workflow_engine), headers={"X-FraudSentinel-Sandbox": "synthetic-only"}
    ) as client:
        yield client


@pytest.mark.parametrize(
    "name,score,category",
    [
        ("normal", "0", "low"),
        ("large", "25", "medium"),
        ("timing", "15", "low"),
        ("high", "85", "critical"),
    ],
)
def test_scenarios_have_explainable_expected_scores(repo, name, score, category):
    result = DetectionService(repo).analyze(f"scenario_{name}")
    assessment = result["assessment"]
    assert Decimal(assessment["score"]) == Decimal(score)
    assert assessment["risk_category"] == category
    assert sum(Decimal(f["contribution"]) for f in assessment["factors"]) == Decimal(score)
    assert (
        repo.session.get(RiskAssessment, assessment["assessment_id"]).risk_score
        == Decimal(score) / 100
    )
    for factor in assessment["factors"]:
        assert f"scenario_{name}" in factor["source_transaction_ids"]
        repo._validate_sources(factor["source_transaction_ids"])


def test_replay_duplicate_analysis_and_versioned_history(repo):
    service = DetectionService(repo)
    first = service.analyze("scenario_high")
    second = service.analyze("scenario_high")
    assert first == second
    snapshot = first["analysis"]
    assert fingerprint(snapshot) == first["fingerprint"]
    factors, missing, status = evaluate(
        snapshot["target"],
        snapshot["history"],
        Rules.model_validate(snapshot["configuration"]),
        snapshot["truncated"],
    )
    assert factors == first["assessment"]["factors"]
    assert missing == first["assessment"]["missing_information"]
    assert status == first["assessment"]["status"]


def test_changed_valid_rules_preserve_assessment_history(repo):
    first = DetectionService(repo).analyze("scenario_large")
    second = DetectionService(repo, Rules(version="rules_v2", amount_ratio="100")).analyze(
        "scenario_large"
    )
    assert first["assessment"]["assessment_id"] != second["assessment"]["assessment_id"]
    assert len(repo.list_assessments("scenario_large")) == 2
    assert (
        repo.session.get(AnalysisRun, first["assessment"]["assessment_id"]).snapshot
        == first["analysis"]
    )


def test_future_other_currency_and_missing_context_are_not_fraud(repo):
    current = repo.get_transaction("scenario_normal").model_dump(exclude={"case_id", "created_at"})
    current.update(
        transaction_id="missing_context",
        source_account_id="scenario_other",
        amount="999999.00",
        currency="USD",
        device_id=None,
        location=None,
        payment_channel=None,
    )
    repo.create_transaction(TransactionCreate(**current))
    result = DetectionService(repo).analyze("missing_context")
    assert result["assessment"]["score"] == "0.00"
    assert result["assessment"]["status"] == "insufficient_history"
    assert "scenario_high" not in [h["transaction_id"] for h in result["analysis"]["history"]]
    assert all(
        h["occurred_at"] < result["analysis"]["target"]["occurred_at"]
        for h in result["analysis"]["history"]
    )


def test_bounded_history_is_explicit(repo):
    result = DetectionService(repo, Rules(history_limit=5)).analyze("scenario_high")
    assert result["analysis"]["truncated"]
    assert len(result["analysis"]["history"]) == 5
    assert result["assessment"]["status"] == "insufficient_history"


def test_graph_records_chains_cycles_repetition_shared_context_and_bounds(repo):
    graph = RelationshipService(repo).graph("scenario_sender", GraphQuery(depth=3))
    types = {f["type"] for f in graph["findings"]}
    assert {"directed_cycle", "fan_out", "repeated_transfers", "shared_device"} <= types
    for finding in graph["findings"]:
        repo._validate_sources(finding["source_transaction_ids"])
    limited = RelationshipService(repo).graph("scenario_sender", GraphQuery(limit=1))
    assert limited["truncated"] and limited["transaction_count"] == 1
    assert graph["edges"] and all(
        e["transaction_count"] == len(e["transaction_ids"]) for e in graph["edges"]
    )


def test_evidence_is_deduplicated_and_cites_assessment_sources(repo):
    assessment = DetectionService(repo).analyze("scenario_high")["assessment"]
    service = EvidenceService(repo)
    first = service.collect(assessment["assessment_id"])
    second = service.collect(assessment["assessment_id"])
    assert [e.evidence_id for e in first] == [e.evidence_id for e in second]
    assert len(first) == len(assessment["factors"])
    assert all(
        e.verification_status == "unverified" and e.assessment_id == assessment["assessment_id"]
        for e in first
    )
    assert all("scenario_high" in e.provenance.source_transaction_ids for e in first)


def test_workflow_report_links_notes_transitions_and_immutable_history(repo):
    assessment = DetectionService(repo).analyze("scenario_high")["assessment"]
    evidence = EvidenceService(repo).collect(assessment["assessment_id"])
    service = InvestigationService(repo)
    case = service.create(
        InvestigationCreate(
            case_id="investigation",
            title="Synthetic review",
            assessment_ids=[assessment["assessment_id"]],
            evidence_ids=[e.evidence_id for e in evidence],
            account_ids=["scenario_sender"],
        )
    )
    assert repo.get_transaction("scenario_high").case_id == case["case_id"]
    assert all(repo.get_evidence(e.evidence_id).case_id == case["case_id"] for e in evidence)
    service.note(case["case_id"], "Analyst observation, not verified fact")
    for state in ("under_investigation", "pending_review", "resolved"):
        case = service.get(case["case_id"])
        service.update(case["case_id"], CasePatch(expected_version=case["version"], status=state))
    report = service.report(case["case_id"])
    assert service.report(case["case_id"])["report_id"] == report["report_id"]
    assert report["fingerprint"] == fingerprint(report["content"])
    assert (
        report["content"]["recorded_facts"]["transactions"][0]["transaction_id"] == "scenario_high"
    )
    assert (
        report["content"]["analyst_notes"][0]["description"]
        == "Analyst observation, not verified fact"
    )
    assert (
        report["content"]["system_findings"]["assessments"][0]["assessment_id"]
        == assessment["assessment_id"]
    )
    service.note(case["case_id"], "A second review note")
    newer = service.report(case["case_id"])
    assert newer["report_id"] != report["report_id"]
    assert service.get_report(case["case_id"], report["report_id"]) == report
    assert any(
        e["kind"] == "report_generated" for e in service.timeline(case["case_id"], Page(limit=100))
    )


def test_conflicting_case_links_stale_updates_and_invalid_status_are_refused(repo):
    service = InvestigationService(repo)
    first = service.create(
        InvestigationCreate(case_id="first", title="First", transaction_ids=["scenario_high"])
    )
    service.create(InvestigationCreate(case_id="second", title="Second"))
    with pytest.raises(Conflict):
        service.link("second", CaseLinks(transaction_ids=["scenario_high"]))
    with pytest.raises(Conflict):
        service.update("first", CasePatch(expected_version=first["version"], status="resolved"))
    service.note("first", "New state")
    with pytest.raises(Conflict):
        service.update("first", CasePatch(expected_version=first["version"], title="Stale title"))
    current = service.get("first")
    service.update("first", CasePatch(expected_version=current["version"], status="closed"))
    with pytest.raises(Conflict):
        service.note("first", "Closed mutation")


def test_cross_scope_every_service_and_reviewer_denial(repo):
    result = DetectionService(repo).analyze("scenario_high")["assessment"]
    evidence = EvidenceService(repo).collect(result["assessment_id"])[0]
    service = InvestigationService(repo)
    service.create(InvestigationCreate(case_id="private_case", title="Private"))
    report = service.report("private_case")
    repo.session.add_all(
        [
            User(user_id="other", display_name="Other", role="investigator"),
            User(user_id="reader", display_name="Reader", role="reviewer"),
        ]
    )
    repo.session.flush()
    other = IntelligenceRepository(repo.session, "other")
    for action in [
        lambda: DetectionService(other).analyze("scenario_high"),
        lambda: RelationshipService(other).graph("scenario_sender"),
        lambda: other.get_evidence(evidence.evidence_id),
        lambda: InvestigationService(other).get("private_case"),
        lambda: InvestigationService(other).get_report("private_case", report["report_id"]),
    ]:
        with pytest.raises(ResourceNotFound):
            action()
    assert EvidenceService(other).list(Page()) == []
    assert InvestigationService(other).list(Page()) == []
    reader = IntelligenceRepository(repo.session, "reader")
    with pytest.raises(AccessDenied):
        DetectionService(reader).analyze("scenario_high")
    with pytest.raises(AccessDenied):
        InvestigationService(reader).create(InvestigationCreate(case_id="denied", title="Denied"))


def test_api_complete_synthetic_workflow(sandbox):
    base = "/api/v1/intelligence"
    for account in ("api_sender", "api_receiver"):
        assert (
            sandbox.post(
                base + "/accounts",
                json={"account_id": account, "data_source": "test", "is_synthetic": True},
            ).status_code
            == 201
        )
    transfer = {
        "transaction_id": "api_tx",
        "source_account_id": "api_sender",
        "destination_account_id": "api_receiver",
        "amount": "100.00",
        "currency": "INR",
        "occurred_at": "2026-11-17T12:00:00Z",
        "transaction_type": "transfer",
        "status": "completed",
        "data_source": "test",
        "is_synthetic": True,
    }
    assert sandbox.post(base + "/transactions", json=transfer).status_code == 201
    analyzed = sandbox.post(base + "/transactions/api_tx/analyze")
    assert analyzed.status_code == 200
    assessment = analyzed.json()["assessment"]
    assert sandbox.get(base + "/accounts/api_sender/relationships").status_code == 200
    evidence = {
        "evidence_id": "api_evidence",
        "transaction_id": "api_tx",
        "assessment_id": assessment["assessment_id"],
        "description": "Observed synthetic transfer",
        "source": "test",
        "kind": "observed_fact",
        "method": "fixture",
        "provenance": {
            "source_reference": "transaction:api_tx",
            "source_transaction_ids": ["api_tx"],
            "observed_at": "2026-11-17T12:00:00Z",
        },
    }
    assert sandbox.post(base + "/evidence", json=evidence).status_code == 201
    created = sandbox.post(
        base + "/cases",
        json={
            "case_id": "api_case",
            "title": "API investigation",
            "transaction_ids": ["api_tx"],
            "evidence_ids": ["api_evidence"],
            "account_ids": ["api_sender"],
        },
    )
    assert created.status_code == 201, created.text
    updated = sandbox.patch(
        base + "/cases/api_case",
        json={"expected_version": created.json()["version"], "status": "under_investigation"},
    )
    assert updated.status_code == 200
    assert (
        sandbox.post(
            base + "/cases/api_case/notes", json={"text": "Review actual source records"}
        ).status_code
        == 201
    )
    report = sandbox.post(base + "/cases/api_case/reports")
    assert report.status_code == 200, report.text
    assert (
        sandbox.get(base + f"/cases/api_case/reports/{report.json()['report_id']}").json()
        == report.json()
    )
    assert sandbox.get(base + "/evidence?case_id=api_case").json()[0]["transaction_id"] == "api_tx"
    assert sandbox.get(base + "/dashboard").status_code == 200


@pytest.mark.parametrize(
    "path",
    [
        "/transactions?limit=0",
        "/transactions?offset=10001",
        "/cases?status=fraud_confirmed",
        "/accounts/scenario_sender/relationships?depth=9",
        "/evidence?limit=101",
    ],
)
def test_api_rejects_invalid_filters(sandbox, path):
    assert sandbox.get("/api/v1/intelligence" + path).status_code == 422


def test_api_safe_errors_atomic_rollback_and_csrf(sandbox, workflow_engine):
    base = "/api/v1/intelligence"
    denied = sandbox.post(
        base + "/cases",
        json={"case_id": "blocked", "title": "No"},
        headers={"Origin": "https://attacker.example"},
    )
    assert denied.status_code == 403
    response = sandbox.post(
        base + "/cases",
        json={"case_id": "atomic", "title": "Atomic", "transaction_ids": ["missing"]},
    )
    assert response.status_code == 404
    with Session(workflow_engine) as session:
        assert session.get(Case, "atomic") is None
    private = "DO_NOT_ECHO_PRIVATE_VALUE"
    response = sandbox.post(
        base + "/cases", json={"case_id": "bad", "title": "Bad", "owner_id": private}
    )
    assert response.status_code == 422 and private not in response.text
    assert sandbox.get(base + "/transactions/unknown").status_code == 404


def test_disabled_sandbox_cannot_access_database(client, engine):
    from unittest.mock import patch

    with patch.object(engine, "connect", side_effect=AssertionError("No database access allowed")):
        assert (
            client.post("/api/v1/intelligence/transactions/scenario_high/analyze").status_code
            == 403
        )
        assert client.get("/api/v1/intelligence/cases").status_code == 403
    assert client.get("/api/v1/intelligence/capabilities").json()["enabled"] is False


def test_repeated_links_preserve_case_version_and_timeline(repo):
    service = InvestigationService(repo)
    case = service.create(
        InvestigationCreate(
            case_id="repeat",
            title="Repeat",
            transaction_ids=["scenario_normal"],
            account_ids=["scenario_sender"],
        )
    )
    before = service.timeline("repeat", Page(limit=100))
    repeated = service.link(
        "repeat", CaseLinks(transaction_ids=["scenario_normal"], account_ids=["scenario_sender"])
    )
    assert repeated["version"] == case["version"]
    assert service.timeline("repeat", Page(limit=100)) == before


def test_closed_case_rejects_new_analysis_and_evidence_but_allows_report(repo):
    service = InvestigationService(repo)
    assessment = DetectionService(repo).analyze("scenario_high")["assessment"]
    case = service.create(
        InvestigationCreate(
            case_id="closed_case", title="Closed", transaction_ids=["scenario_high"]
        )
    )
    service.update("closed_case", CasePatch(expected_version=case["version"], status="closed"))
    with pytest.raises(Conflict):
        DetectionService(repo).analyze("scenario_high")
    with pytest.raises(Conflict):
        EvidenceService(repo).collect(assessment["assessment_id"])
    assert service.report("closed_case")["content"]["case"]["status"] == "closed"


def test_report_rechecks_evidence_source_cases_and_never_invents_verification(repo):
    service = InvestigationService(repo)
    assessment = DetectionService(repo).analyze("scenario_high")["assessment"]
    evidence = EvidenceService(repo).collect(assessment["assessment_id"])
    service.create(
        InvestigationCreate(
            case_id="source_review",
            title="Source review",
            transaction_ids=["scenario_high"],
            evidence_ids=[e.evidence_id for e in evidence],
        )
    )
    report = service.report("source_review")
    assert report["content"]["verified_facts"] == []
    assert len(report["content"]["supporting_source_transactions"]) > 1
    service.create(
        InvestigationCreate(
            case_id="different_review", title="Different", transaction_ids=["scenario_baseline_0"]
        )
    )
    with pytest.raises(Conflict, match="crosses another investigation"):
        service.report("source_review")


def test_api_case_lists_history_and_reports_are_scoped_and_paginated(sandbox):
    base = "/api/v1/intelligence"
    for name in ("page_a", "page_b"):
        assert (
            sandbox.post(base + "/cases", json={"case_id": name, "title": name}).status_code == 201
        )
    first = sandbox.get(base + "/cases?limit=1&offset=0").json()
    second = sandbox.get(base + "/cases?limit=1&offset=1").json()
    assert len(first) == len(second) == 1 and first[0]["case_id"] != second[0]["case_id"]
    assert sandbox.get(base + "/cases/page_a/transactions").json() == []
    assert sandbox.post(base + "/cases/page_a/reports").status_code == 200
    assert len(sandbox.get(base + "/cases/page_a/reports").json()) == 1
    assert len(sandbox.get(base + "/transactions/scenario_high/assessments?limit=1").json()) == 1
    assert (
        sandbox.get(base + "/transactions/scenario_high/assessments?limit=1&offset=1").json() == []
    )
