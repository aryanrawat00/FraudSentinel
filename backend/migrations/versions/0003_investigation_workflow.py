"""Add reproducible analysis, evidence deduplication and investigation history.

No existing records, columns, constraints or relationships are changed.
Apply to the active database only after separate migration approval.
"""

import sqlalchemy as sa
from alembic import op

revision = "0003_investigation_workflow"
down_revision = "0002_intelligence_contracts"
branch_labels = None
depends_on = None


def upgrade():
    if op.get_bind().dialect.name != "postgresql":
        raise RuntimeError("PostgreSQL is required for reviewed migrations")
    op.create_table(
        "analysis_runs",
        sa.Column(
            "assessment_id",
            sa.String(64),
            sa.ForeignKey(
                "risk_assessments.assessment_id",
                name="fk_analysis_runs_assessment_id_risk_assessments",
            ),
            primary_key=True,
        ),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.UniqueConstraint("fingerprint", name="uq_analysis_runs_fingerprint"),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("assessment_id", name="pk_analysis_runs"),
    )
    op.create_table(
        "case_workflows",
        sa.Column("case_id", sa.String(64), primary_key=True),
        sa.Column("owner_id", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column(
            "assigned_to",
            sa.String(64),
            sa.ForeignKey("users.user_id", name="fk_case_workflows_assigned_to_users"),
            nullable=True,
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["case_id", "owner_id"],
            ["cases.case_id", "cases.owner_id"],
            name="fk_case_workflows_scope",
        ),
        sa.CheckConstraint(
            "status IN ('open','under_investigation','pending_review','resolved','closed')",
            name=op.f("ck_case_workflows_status"),
        ),
        sa.CheckConstraint("version >= 1", name=op.f("ck_case_workflows_version")),
        sa.PrimaryKeyConstraint("case_id", name="pk_case_workflows"),
    )
    op.create_index("ix_case_workflows_owner_id", "case_workflows", ["owner_id"])
    op.create_table(
        "case_events",
        sa.Column("event_id", sa.String(64), primary_key=True),
        sa.Column(
            "case_id",
            sa.String(64),
            sa.ForeignKey("cases.case_id", name="fk_case_events_case_id_cases"),
            nullable=False,
        ),
        sa.Column(
            "actor_id",
            sa.String(64),
            sa.ForeignKey("users.user_id", name="fk_case_events_actor_id_users"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(40), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("references", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("event_id", name="pk_case_events"),
    )
    op.create_index("ix_case_events_case_id", "case_events", ["case_id"])
    op.create_table(
        "investigation_reports",
        sa.Column("report_id", sa.String(64), primary_key=True),
        sa.Column(
            "case_id",
            sa.String(64),
            sa.ForeignKey("cases.case_id", name="fk_investigation_reports_case_id_cases"),
            nullable=False,
        ),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.UniqueConstraint("fingerprint", name="uq_investigation_reports_fingerprint"),
        sa.Column("content", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("report_id", name="pk_investigation_reports"),
    )
    op.create_index("ix_investigation_reports_case_id", "investigation_reports", ["case_id"])
    op.create_table(
        "evidence_fingerprints",
        sa.Column(
            "evidence_id",
            sa.String(64),
            sa.ForeignKey(
                "evidence.evidence_id", name="fk_evidence_fingerprints_evidence_id_evidence"
            ),
            primary_key=True,
        ),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.UniqueConstraint("fingerprint", name="uq_evidence_fingerprints_fingerprint"),
        sa.PrimaryKeyConstraint("evidence_id", name="pk_evidence_fingerprints"),
    )


def downgrade():
    raise RuntimeError("Forward-only: preserve investigation history; no downgrade is permitted")
