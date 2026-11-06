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
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = {column["name"] for column in inspector.get_columns("categories")}
    if "icon" not in columns:
        with op.batch_alter_table("categories") as batch:
            batch.add_column(sa.Column("icon", sa.String(40), nullable=True))


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = {column["name"] for column in inspector.get_columns("categories")}
    if "icon" in columns:
        with op.batch_alter_table("categories") as batch:
            batch.drop_column("icon")
