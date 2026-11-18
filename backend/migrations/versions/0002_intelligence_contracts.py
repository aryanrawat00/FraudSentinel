"""Expand persistence for account-aware ingestion and explainable assessments.

Forward-only by design: rolling back these additions could destroy Phase 2 data.
The upgrade never deletes rows or tables. Review before applying to existing data.
"""

import sqlalchemy as sa
from alembic import op

revision = "0002_intelligence_contracts"
down_revision = "0001_foundation"
branch_labels = None
depends_on = None


def upgrade():
    if op.get_bind().dialect.name != "postgresql":
        raise RuntimeError(
            "This migration requires PostgreSQL; SQLite is for model/unit tests only"
        )

    op.create_unique_constraint("uq_cases_case_owner", "cases", ["case_id", "owner_id"])
    op.add_column("cases", sa.Column("description", sa.Text(), nullable=False, server_default=""))
    op.add_column(
        "cases", sa.Column("priority", sa.String(16), nullable=False, server_default="medium")
    )
    op.add_column("cases", sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True))
    op.create_check_constraint(
        "priority", "cases", "priority IN ('low', 'medium', 'high', 'urgent')"
    )

    op.create_table(
        "accounts",
        sa.Column("account_id", sa.String(64), primary_key=True),
        sa.Column("owner_id", sa.String(64), sa.ForeignKey("users.user_id"), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("data_source", sa.String(100), nullable=False),
        sa.Column("is_synthetic", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("account_id", "owner_id", name="uq_accounts_account_owner"),
        sa.CheckConstraint("status IN ('unknown', 'active', 'inactive', 'closed')", name="status"),
    )
    op.create_index("ix_accounts_owner_id", "accounts", ["owner_id"])
    op.create_table(
        "case_accounts",
        sa.Column("case_id", sa.String(64), primary_key=True),
        sa.Column("account_id", sa.String(64), primary_key=True),
        sa.Column("owner_id", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["case_id", "owner_id"],
            ["cases.case_id", "cases.owner_id"],
            name="fk_case_accounts_case_scope",
        ),
        sa.ForeignKeyConstraint(
            ["account_id", "owner_id"],
            ["accounts.account_id", "accounts.owner_id"],
            name="fk_case_accounts_account_scope",
        ),
    )
    op.create_index("ix_case_accounts_owner_id", "case_accounts", ["owner_id"])

    for name in ["case_id", "customer_id", "device_id", "beneficiary_id"]:
        op.alter_column("transactions", name, existing_type=sa.String(64), nullable=True)
    for column in [
        sa.Column("owner_id", sa.String(64), sa.ForeignKey("users.user_id"), nullable=True),
        sa.Column("source_account_id", sa.String(64), nullable=True),
        sa.Column("destination_account_id", sa.String(64), nullable=True),
        sa.Column("transaction_type", sa.String(24), nullable=False, server_default="unknown"),
        sa.Column("status", sa.String(24), nullable=False, server_default="unknown"),
        sa.Column("payment_channel", sa.String(32), nullable=True),
        sa.Column("location", sa.JSON(), nullable=True),
        sa.Column(
            "data_source", sa.String(100), nullable=False, server_default="legacy_unspecified"
        ),
        sa.Column("is_synthetic", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    ]:
        op.add_column("transactions", column)
    # Only copy existing ownership facts. Customer/beneficiary IDs are NOT assumed
    # to be bank accounts; account mapping, creation time and provenance stay unknown.
    op.execute(
        sa.text(
            "UPDATE transactions SET owner_id = cases.owner_id FROM cases "
            "WHERE transactions.case_id = cases.case_id AND transactions.owner_id IS NULL"
        )
    )
    for name in ["owner_id", "source_account_id", "destination_account_id"]:
        op.create_index(f"ix_transactions_{name}", "transactions", [name])
    op.create_check_constraint(
        "access_scope", "transactions", "owner_id IS NOT NULL OR case_id IS NOT NULL"
    )
    op.create_check_constraint(
        "account_pair",
        "transactions",
        "(source_account_id IS NULL AND destination_account_id IS NULL) OR "
        "(source_account_id IS NOT NULL AND destination_account_id IS NOT NULL "
        "AND owner_id IS NOT NULL)",
    )
    op.create_foreign_key(
        "fk_transactions_case_scope",
        "transactions",
        "cases",
        ["case_id", "owner_id"],
        ["case_id", "owner_id"],
    )
    for side in ["source", "destination"]:
        op.create_foreign_key(
            f"fk_transactions_{side}_scope",
            "transactions",
            "accounts",
            [f"{side}_account_id", "owner_id"],
            ["account_id", "owner_id"],
        )

    op.create_unique_constraint(
        "uq_assessments_transaction", "risk_assessments", ["assessment_id", "transaction_id"]
    )
    for column in [
        sa.Column("risk_category", sa.String(16), nullable=True),
        sa.Column("method", sa.String(32), nullable=False, server_default="legacy"),
        sa.Column("status", sa.String(32), nullable=False, server_default="legacy"),
        sa.Column("factors", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("missing_information", sa.JSON(), nullable=False, server_default="[]"),
    ]:
        op.add_column("risk_assessments", column)
    # risk_score remains Numeric(5,4), 0..1. Contract conversion is explicit x100.

    op.alter_column("evidence", "case_id", existing_type=sa.String(64), nullable=True)
    for column in [
        sa.Column("assessment_id", sa.String(64), nullable=True),
        sa.Column("account_id", sa.String(64), sa.ForeignKey("accounts.account_id"), nullable=True),
        sa.Column("kind", sa.String(32), nullable=False, server_default="legacy"),
        sa.Column("method", sa.String(64), nullable=False, server_default="legacy"),
        sa.Column(
            "verification_status", sa.String(24), nullable=False, server_default="unverified"
        ),
        sa.Column("provenance", sa.JSON(), nullable=False, server_default="{}"),
    ]:
        op.add_column("evidence", column)
    for name in ["assessment_id", "account_id"]:
        op.create_index(f"ix_evidence_{name}", "evidence", [name])
    op.create_foreign_key(
        "fk_evidence_source_transaction",
        "evidence",
        "transactions",
        ["transaction_id"],
        ["transaction_id"],
    )
    op.create_foreign_key(
        "fk_evidence_assessment_transaction",
        "evidence",
        "risk_assessments",
        ["assessment_id", "transaction_id"],
        ["assessment_id", "transaction_id"],
    )
    op.create_check_constraint(
        "association", "evidence", "case_id IS NOT NULL OR assessment_id IS NOT NULL"
    )


def downgrade():
    raise RuntimeError(
        "Automatic downgrade is disabled because it would discard Phase 2 records. "
        "Use a separately reviewed forward repair or authorized backup restoration."
    )
