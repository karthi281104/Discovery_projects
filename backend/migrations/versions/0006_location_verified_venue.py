"""add is_verified_venue to locations

Revision ID: 0006_location_verified_venue
Revises: 0005_repair_category_icon
Create Date: 2026-11-06
"""
from alembic import op
import sqlalchemy as sa

revision = "0006_location_verified_venue"
down_revision = "0005_repair_category_icon"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    insp = sa.inspect(conn)
    loc_cols = {c["name"] for c in insp.get_columns("locations")}
    with op.batch_alter_table("locations") as batch:
        if "is_verified_venue" not in loc_cols:
            batch.add_column(
                sa.Column("is_verified_venue", sa.Boolean(), nullable=False, server_default=sa.false())
            )


def downgrade():
    conn = op.get_bind()
    insp = sa.inspect(conn)
    loc_cols = {c["name"] for c in insp.get_columns("locations")}
    with op.batch_alter_table("locations") as batch:
        if "is_verified_venue" in loc_cols:
            batch.drop_column("is_verified_venue")

