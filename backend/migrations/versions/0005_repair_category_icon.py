"""repair category icon column for databases stamped at 0004

Revision ID: 0005_repair_category_icon
Revises: 0004_complete_milestone2_schema
"""
from alembic import op
import sqlalchemy as sa

revision = "0005_repair_category_icon"
down_revision = "0004_complete_milestone2_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("categories")}
    if "icon" not in columns:
        op.add_column("categories", sa.Column("icon", sa.String(40), nullable=True))


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("categories")}
    if "icon" in columns:
        op.drop_column("categories", "icon")
