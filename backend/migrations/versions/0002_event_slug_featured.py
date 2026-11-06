from alembic import op
import sqlalchemy as sa

revision = "0002_event_slug_featured"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("events", sa.Column("slug", sa.String(280), nullable=True))
    op.add_column("events", sa.Column("is_featured", sa.Boolean(), nullable=False, server_default=sa.false()))
    connection = op.get_bind()
    connection.execute(sa.text("UPDATE events SET slug = 'event-' || CAST(id AS VARCHAR(50)) WHERE slug IS NULL"))
    op.create_index("ix_events_slug", "events", ["slug"], unique=True)


def downgrade():
    op.drop_index("ix_events_slug", table_name="events")
    op.drop_column("events", "is_featured")
    op.drop_column("events", "slug")
