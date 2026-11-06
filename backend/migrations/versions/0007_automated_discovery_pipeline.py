"""automated discovery pipeline models

Revision ID: 0007_disc_pipeline
Revises: 0006_location_verified_venue
Create Date: 2026-11-06
"""
from alembic import op
import sqlalchemy as sa

revision = "0007_disc_pipeline"
down_revision = "0006_location_verified_venue"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    existing_tables = set(sa.inspect(conn).get_table_names())

    if "discovery_sources" not in existing_tables:
        op.create_table(
            "discovery_sources",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("name", sa.String(length=160), nullable=False),
            sa.Column("base_url", sa.String(length=500), nullable=False),
            sa.Column("source_type", sa.String(length=40), nullable=False),
            sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("region", sa.String(length=120), nullable=False, server_default="Tamil Nadu"),
            sa.Column("crawl_interval", sa.Integer(), nullable=False, server_default="60"),
            sa.Column("request_config", sa.JSON(), nullable=False, server_default="{}"),
            sa.Column("last_crawl_time", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_success_time", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_error", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("ix_discovery_sources_name", "discovery_sources", ["name"], unique=True)
        op.create_index("ix_discovery_sources_source_type", "discovery_sources", ["source_type"])
        op.create_index("ix_discovery_sources_is_enabled", "discovery_sources", ["is_enabled"])

    if "discovery_runs" not in existing_tables:
        op.create_table(
            "discovery_runs",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("source_id", sa.Integer(), sa.ForeignKey("discovery_sources.id", ondelete="CASCADE"), nullable=True),
            sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("status", sa.String(length=30), nullable=False, server_default="running"),
            sa.Column("pages_checked", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("candidates_found", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("events_created", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("events_updated", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("duplicates_skipped", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("validation_failures", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("metrics", sa.JSON(), nullable=False, server_default="{}"),
        )
        op.create_index("ix_discovery_runs_source_id", "discovery_runs", ["source_id"])
        op.create_index("ix_discovery_runs_started_at", "discovery_runs", ["started_at"])
        op.create_index("ix_discovery_runs_status", "discovery_runs", ["status"])

    if "event_sources" not in existing_tables:
        op.create_table(
            "event_sources",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("event_id", sa.Integer(), sa.ForeignKey("events.id", ondelete="CASCADE"), nullable=False),
            sa.Column("source_id", sa.Integer(), sa.ForeignKey("discovery_sources.id", ondelete="CASCADE"), nullable=False),
            sa.Column("external_event_id", sa.String(length=250), nullable=True),
            sa.Column("source_event_url", sa.String(length=1000), nullable=False),
            sa.Column("canonical_url", sa.String(length=1000), nullable=False),
            sa.Column("content_hash", sa.String(length=64), nullable=False),
            sa.Column("first_seen", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("last_seen", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("last_checked", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("ix_event_sources_event_id", "event_sources", ["event_id"])
        op.create_index("ix_event_sources_source_id", "event_sources", ["source_id"])
        op.create_index("ix_event_sources_canonical_url", "event_sources", ["canonical_url"])
        op.create_index("ix_event_sources_external_event_id", "event_sources", ["external_event_id"])

    if "event_snapshots" not in existing_tables:
        op.create_table(
            "event_snapshots",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("event_source_id", sa.Integer(), sa.ForeignKey("event_sources.id", ondelete="CASCADE"), nullable=False),
            sa.Column("raw_payload", sa.JSON(), nullable=False, server_default="{}"),
            sa.Column("content_hash", sa.String(length=64), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("ix_event_snapshots_event_source_id", "event_snapshots", ["event_source_id"])
        op.create_index("ix_event_snapshots_created_at", "event_snapshots", ["created_at"])


def downgrade():
    existing_tables = set(sa.inspect(op.get_bind()).get_table_names())
    for table_name in ("event_snapshots", "event_sources", "discovery_runs", "discovery_sources"):
        if table_name in existing_tables:
            op.drop_table(table_name)
