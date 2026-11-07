"""Add autonomous state contracts: search_query_executions, discovered_urls, and event tracking fields

Revision ID: 0009_autonomous_state_contracts
Revises: 0008_autonomous_search
Create Date: 2026-11-07
"""
from alembic import op
import sqlalchemy as sa

revision = "0009_autonomous_state_contracts"
down_revision = "0008_autonomous_search"
branch_labels = None
depends_on = None


def upgrade():
    # 1. Create search_query_executions table
    op.create_table(
        "search_query_executions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("query_text", sa.String(length=500), nullable=False),
        sa.Column("language", sa.String(length=20), nullable=True),
        sa.Column("category", sa.String(length=100), nullable=True),
        sa.Column("location_target", sa.String(length=100), nullable=True),
        sa.Column("page_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("results_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("new_urls_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("yield_score", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("executed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_search_query_executions_query_text", "search_query_executions", ["query_text"])
    op.create_index("ix_search_query_executions_executed_at", "search_query_executions", ["executed_at"])
    op.create_index(
        "uq_search_query_exec_day",
        "search_query_executions",
        ["query_text", "page_number", sa.text("CAST(executed_at AS DATE)")],
        unique=True,
    )

    # 2. Create discovered_urls table
    op.create_table(
        "discovered_urls",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("raw_url", sa.Text(), nullable=False),
        sa.Column("canonical_url", sa.Text(), nullable=False),
        sa.Column("domain", sa.String(length=255), nullable=False),
        sa.Column("classification", sa.String(length=50), nullable=False, server_default="event_page"),
        sa.Column("fetch_status", sa.String(length=30), nullable=False, server_default="pending"),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column("discovered_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_discovered_urls_canonical_url", "discovered_urls", ["canonical_url"], unique=True)
    op.create_index("ix_discovered_urls_domain", "discovered_urls", ["domain"])
    op.create_index("ix_discovered_urls_fetch_status", "discovered_urls", ["fetch_status"])

    # 3. Update events table with autonomous tracking fields
    with op.batch_alter_table("events", schema=None) as batch_op:
        batch_op.add_column(sa.Column("original_source_url", sa.Text(), nullable=False, server_default=""))
        batch_op.add_column(sa.Column("additional_source_urls", sa.JSON(), nullable=False, server_default="[]"))
        batch_op.add_column(sa.Column("confidence_score", sa.Float(), nullable=False, server_default="0.0"))
        batch_op.add_column(sa.Column("validation_outcome", sa.String(length=50), nullable=True, server_default="auto_published"))
        batch_op.add_column(sa.Column("content_hash", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("update_history", sa.JSON(), nullable=False, server_default="[]"))
        batch_op.add_column(sa.Column("discovered_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("extracted_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.create_index("ix_events_content_hash", ["content_hash"])


def downgrade():
    with op.batch_alter_table("events", schema=None) as batch_op:
        batch_op.drop_index("ix_events_content_hash")
        batch_op.drop_column("verified_at")
        batch_op.drop_column("extracted_at")
        batch_op.drop_column("discovered_at")
        batch_op.drop_column("update_history")
        batch_op.drop_column("content_hash")
        batch_op.drop_column("validation_outcome")
        batch_op.drop_column("confidence_score")
        batch_op.drop_column("additional_source_urls")
        batch_op.drop_column("original_source_url")

    op.drop_table("discovered_urls")
    op.drop_table("search_query_executions")

