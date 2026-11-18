"""Explainable rules, never a fraud verdict or a calibrated probability."""

import hashlib
import json
from datetime import UTC, timedelta
from decimal import Decimal
from statistics import median
from typing import Annotated

from pydantic import Field, model_validator

from app.models import Transaction
from app.models.workflow import AnalysisRun
from app.repositories.intelligence import IntelligenceRepository
from app.schemas.intelligence import AssessmentCreate, Contract, Identifier, Score
from app.services.access import lock_mutable_transaction


class Rules(Contract):
    version: Identifier = "rules_v1"
    history_days: Annotated[int, Field(ge=1, le=365)] = 30
    history_limit: Annotated[int, Field(ge=5, le=99)] = 99
    min_history: Annotated[int, Field(ge=3, le=99)] = 5
    amount_ratio: Annotated[Decimal, Field(gt=1, le=100)] = Decimal("5")
    burst_minutes: Annotated[int, Field(ge=1, le=60)] = 10
    burst_count: Annotated[int, Field(ge=2, le=100)] = 4
    fanout_count: Annotated[int, Field(ge=2, le=100)] = 3
    hour_distance: Annotated[int, Field(ge=1, le=12)] = 3
    weights: dict[str, Score] = {
        "AMOUNT_SPIKE": Decimal("25"),
        "RAPID_SEQUENCE": Decimal("25"),
        "UNUSUAL_HOUR": Decimal("15"),
        "NEW_DEVICE": Decimal("10"),
        "NEW_COUNTRY": Decimal("10"),
        "NEW_CHANNEL": Decimal("5"),
        "RAPID_FANOUT": Decimal("10"),
    }
    medium: Score = Decimal("25")
    high: Score = Decimal("50")
    critical: Score = Decimal("75")
    temporal_group_cap: Score = Decimal("35")

    @model_validator(mode="after")
    def consistent(self):
        expected = {
            "AMOUNT_SPIKE",
            "RAPID_SEQUENCE",
            "UNUSUAL_HOUR",
            "NEW_DEVICE",
            "NEW_COUNTRY",
            "NEW_CHANNEL",
            "RAPID_FANOUT",
        }
        if set(self.weights) != expected or sum(self.weights.values()) > 100:
            raise ValueError("All seven rule weights must be configured and total at most 100")
        if not 0 < self.medium < self.high < self.critical <= 100:
            raise ValueError("Category thresholds must increase within 0-100")
        if self.min_history > self.history_limit:
            raise ValueError("Minimum history exceeds the bounded history window")
        return self

    def category(self, score):
        return (
            "critical"
            if score >= self.critical
            else "high"
            if score >= self.high
            else "medium"
            if score >= self.medium
            else "low"
        )


def fingerprint(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def transaction_snapshot(row):
    stamp = row.occurred_at
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=UTC)
    stamp = stamp.astimezone(UTC)
    return {
        "transaction_id": row.transaction_id,
        "source_account_id": row.source_account_id,
        "destination_account_id": row.destination_account_id,
        "customer_id": row.customer_id,
        "amount": str(row.amount),
        "currency": row.currency,
        "occurred_at": stamp.isoformat(),
        "device_id": row.device_id,
        "location": row.location,
        "payment_channel": row.payment_channel,
        "status": row.status,
        "transaction_type": row.transaction_type,
        "data_source": row.data_source,
        "is_synthetic": row.is_synthetic,
    }


def evaluate(target, history, rules: Rules, truncated=False):
    """Pure evaluation over the exact saved input snapshot, in event-time order."""
    from datetime import datetime

    time = datetime.fromisoformat(target["occurred_at"]).astimezone(UTC)
    missing = []
    factors = []
    if truncated:
        missing.append(
            "History exceeds configured limit; only the latest bounded sample was analyzed"
        )
    if not target["source_account_id"] and not target["customer_id"]:
        missing.append(
            "No source account or historical customer reference; behavioral baseline unavailable"
        )
    if not target["device_id"]:
        missing.append("Device context unavailable; absence contributes no risk")
    if not (target["location"] or {}).get("country_code"):
        missing.append("Observed country unavailable; no geographic inference performed")
    if not target["payment_channel"]:
        missing.append("Payment channel unavailable; absence contributes no risk")
    comparable = [
        h
        for h in history
        if h["currency"] == target["currency"]
        and h["transaction_type"] == target["transaction_type"]
    ]
    enough = len(comparable) >= rules.min_history
    if not enough:
        missing.append(
            f"Fewer than {rules.min_history} earlier same-currency/type records; "
            "amount and timing baseline unavailable"
        )
    if target["status"] in {"failed", "reversed", "pending"}:
        missing.append("Transaction is not completed; baseline payment rules were not applied")
        return [], missing, "insufficient_history"

    def add(code, description, sources):
        weight = rules.weights[code]
        if code in {"RAPID_SEQUENCE", "RAPID_FANOUT"}:
            used = sum(
                Decimal(f["contribution"])
                for f in factors
                if f["code"] in {"RAPID_SEQUENCE", "RAPID_FANOUT"}
            )
            weight = min(weight, max(Decimal(0), rules.temporal_group_cap - used))
        if weight:
            factors.append(
                {
                    "code": code,
                    "description": description,
                    "contribution": str(weight),
                    "source_transaction_ids": sorted({target["transaction_id"], *sources}),
                    "review_guidance": (
                        "Verify source records and legitimate explanations with an authorized "
                        "investigator; this is not proof of fraud."
                    ),
                }
            )

    if enough:
        base = median(Decimal(h["amount"]) for h in comparable)
        if Decimal(target["amount"]) >= base * rules.amount_ratio:
            add(
                "AMOUNT_SPIKE",
                f"Amount {target['amount']} {target['currency']} is at least {rules.amount_ratio} "
                f"times the historical median {base} in the same currency/type.",
                [h["transaction_id"] for h in comparable],
            )
        hours = [datetime.fromisoformat(h["occurred_at"]).astimezone(UTC).hour for h in comparable]
        if all(
            min(abs(time.hour - h), 24 - abs(time.hour - h)) >= rules.hour_distance for h in hours
        ):
            add(
                "UNUSUAL_HOUR",
                "UTC hour differs from every observed historical activity hour; "
                "local timezone is unknown.",
                [h["transaction_id"] for h in comparable],
            )
    recent = [
        h
        for h in history
        if datetime.fromisoformat(h["occurred_at"]) >= time - timedelta(minutes=rules.burst_minutes)
    ]
    if len(recent) + 1 >= rules.burst_count:
        add(
            "RAPID_SEQUENCE",
            f"At least {len(recent) + 1} observed transactions in {rules.burst_minutes} minutes, "
            "including this transaction.",
            [h["transaction_id"] for h in recent],
        )
    recipients = {h["destination_account_id"] for h in recent if h["destination_account_id"]}
    if target["destination_account_id"]:
        recipients.add(target["destination_account_id"])
    if len(recipients) >= rules.fanout_count:
        add(
            "RAPID_FANOUT",
            f"Transfers reach {len(recipients)} distinct recorded accounts in the rapid sequence; "
            "shared ownership is not inferred.",
            [h["transaction_id"] for h in recent],
        )
    for field, code in [
        ("device_id", "NEW_DEVICE"),
        ("payment_channel", "NEW_CHANNEL"),
        ("location", "NEW_COUNTRY"),
    ]:

        def value(row):
            return (row[field] or {}).get("country_code") if field == "location" else row[field]

        known = [h for h in history if value(h)]
        if (
            len(known) >= rules.min_history
            and value(target)
            and value(target) not in {value(h) for h in known}
        ):
            add(
                code,
                f"Observed {field.replace('_', ' ')} differs from the available earlier records; "
                "a legitimate change remains possible.",
                [h["transaction_id"] for h in known],
            )
    return factors, missing, "complete" if enough and not truncated else "insufficient_history"


class DetectionService:
    def __init__(self, repo: IntelligenceRepository, rules: Rules | None = None):
        self.repo, self.rules = repo, rules or Rules()

    def analyze(self, transaction_id):
        self.repo._write()
        # Locks serialize identical requests; deterministic PK is a second guard.
        target = lock_mutable_transaction(self.repo, transaction_id)
        stamp = target.occurred_at
        statement = self.repo._transactions().where(
            Transaction.occurred_at < stamp,
            Transaction.occurred_at >= stamp - timedelta(days=self.rules.history_days),
            Transaction.status.in_(["completed", "unknown"]),
            Transaction.is_synthetic.is_(target.is_synthetic),
        )
        if target.source_account_id:
            statement = statement.where(Transaction.source_account_id == target.source_account_id)
        elif target.customer_id:
            statement = statement.where(Transaction.customer_id == target.customer_id)
        else:
            statement = statement.where(False)
        rows = list(
            self.repo.session.scalars(
                statement.order_by(
                    Transaction.occurred_at.desc(), Transaction.transaction_id
                ).limit(self.rules.history_limit + 1)
            )
        )
        snapshot = {
            "algorithm": "deterministic_rules_1",
            "target": transaction_snapshot(target),
            "history": [transaction_snapshot(row) for row in rows[: self.rules.history_limit]],
            "truncated": len(rows) > self.rules.history_limit,
            "configuration": self.rules.model_dump(mode="json"),
        }
        digest = fingerprint(snapshot)
        identifier = f"assess_{digest[:48]}"
        existing = self.repo.session.get(AnalysisRun, identifier)
        if existing:
            return self.get(identifier)
        factors, missing, status = evaluate(
            snapshot["target"], snapshot["history"], self.rules, snapshot["truncated"]
        )
        score = sum((Decimal(f["contribution"]) for f in factors), Decimal(0))
        assessment = self.repo.record_assessment(
            AssessmentCreate(
                assessment_id=identifier,
                transaction_id=transaction_id,
                score=score,
                risk_category=self.rules.category(score),
                method="rules",
                ruleset_version=self.rules.version,
                status=status,
                factors=factors,
                missing_information=missing,
            )
        )
        self.repo.session.add(
            AnalysisRun(assessment_id=identifier, fingerprint=digest, snapshot=snapshot)
        )
        self.repo.session.flush()
        return {
            "assessment": assessment.model_dump(mode="json"),
            "analysis": snapshot,
            "fingerprint": digest,
        }

    def get(self, assessment_id):
        row = self.repo._assessment(assessment_id)
        run = self.repo.session.get(AnalysisRun, assessment_id)
        return {
            "assessment": self.repo._read_assessment(row).model_dump(mode="json"),
            "analysis": run.snapshot if run else None,
            "fingerprint": run.fingerprint if run else None,
        }
