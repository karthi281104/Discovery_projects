from alembic import op
import sqlalchemy as sa

revision = "0003_milestone_event_fields"
down_revision = "0002_event_slug_featured"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("events") as batch:
        batch.alter_column("category_id", existing_type=sa.Integer(), nullable=True)
        batch.alter_column("location_id", existing_type=sa.Integer(), nullable=True)
    additions = [
        ("short_description", sa.Text()), ("start_date", sa.DateTime(timezone=True)),
        ("end_date", sa.DateTime(timezone=True)), ("organizer_name", sa.String(180)),
        ("registration_url", sa.String(500)), ("banner_url", sa.String(500)),
        ("event_type", sa.String(40)), ("mode", sa.String(20)), ("status", sa.String(20)),
        ("city", sa.String(120)), ("district", sa.String(120)), ("venue", sa.String(240)),
        ("state", sa.String(120)),
    ]
    for name, column_type in additions:
        op.add_column("events", sa.Column(name, column_type, nullable=True))


def downgrade():
    for name, _ in reversed([
        ("short_description", sa.Text()), ("start_date", sa.DateTime(timezone=True)),
        ("end_date", sa.DateTime(timezone=True)), ("organizer_name", sa.String(180)),
        ("registration_url", sa.String(500)), ("banner_url", sa.String(500)),
        ("event_type", sa.String(40)), ("mode", sa.String(20)), ("status", sa.String(20)),
        ("city", sa.String(120)), ("district", sa.String(120)), ("venue", sa.String(240)),
        ("state", sa.String(120)),
    ]):
        op.drop_column("events", name)
