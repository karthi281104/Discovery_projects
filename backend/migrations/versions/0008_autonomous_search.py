"""persist autonomous search campaigns and results

Revision ID: 0008_autonomous_search
Revises: 0007_automated_discovery_pipeline
Create Date: 2026-11-06
"""
from alembic import op
import sqlalchemy as sa

revision = "0008_autonomous_search"
down_revision = "0007_automated_discovery_pipeline"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "search_campaigns",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("region", sa.String(120), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="running"),
        sa.Column("queries_executed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("results_collected", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sources_discovered", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("duration_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=True),
    )
    op.create_index("ix_search_campaigns_region", "search_campaigns", ["region"])
    op.create_index("ix_search_campaigns_status", "search_campaigns", ["status"])
    op.create_table(
        "search_results",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("campaign_id", sa.Integer(), sa.ForeignKey("search_campaigns.id", ondelete="CASCADE"), nullable=False),
        sa.Column("query", sa.String(500), nullable=False),
        sa.Column("url", sa.String(1000), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("snippet", sa.Text(), nullable=False, server_default=""),
        sa.Column("relevance_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("discovered_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_search_results_campaign_id", "search_results", ["campaign_id"])
    op.create_index("ix_search_results_query", "search_results", ["query"])
    op.create_index("ix_search_results_url", "search_results", ["url"])


def downgrade():
    op.drop_table("search_results")
    op.drop_table("search_campaigns")
