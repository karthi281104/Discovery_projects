"""allow deployed migration identifiers longer than Alembic's default length

Revision ID: 0006_alembic_version_length
Revises: 0006_location_verified_venue
Create Date: 2026-11-06
"""
from alembic import op
import sqlalchemy as sa

revision = "0006_alembic_version_length"
down_revision = "0006_location_verified_venue"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("alembic_version") as batch:
        batch.alter_column(
            "version_num",
            existing_type=sa.String(length=32),
            type_=sa.String(length=64),
            existing_nullable=False,
        )


def downgrade():
    with op.batch_alter_table("alembic_version") as batch:
        batch.alter_column(
            "version_num",
            existing_type=sa.String(length=64),
            type_=sa.String(length=32),
            existing_nullable=False,
        )
