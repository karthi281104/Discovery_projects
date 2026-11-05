from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("categories", sa.Column("id", sa.Integer(), primary_key=True),
                    sa.Column("name", sa.String(120), nullable=False), sa.Column("slug", sa.String(140), nullable=False),
                    sa.Column("description", sa.Text()), sa.UniqueConstraint("name"), sa.UniqueConstraint("slug"))
    op.create_table("locations", sa.Column("id", sa.Integer(), primary_key=True),
                    sa.Column("name", sa.String(180), nullable=False), sa.Column("city", sa.String(120), nullable=False),
                    sa.Column("state", sa.String(120), nullable=False), sa.Column("address", sa.Text()),
                    sa.Column("latitude", sa.Float()), sa.Column("longitude", sa.Float()))
    op.create_table("admin_users", sa.Column("id", sa.Integer(), primary_key=True),
                    sa.Column("email", sa.String(320), nullable=False), sa.Column("password_hash", sa.String(256), nullable=False),
                    sa.Column("is_active", sa.Boolean(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True)),
                    sa.UniqueConstraint("email"))
    op.create_table("events", sa.Column("id", sa.Integer(), primary_key=True),
                    sa.Column("title", sa.String(240), nullable=False), sa.Column("description", sa.Text()),
                    sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False), sa.Column("ends_at", sa.DateTime(timezone=True)),
                    sa.Column("organizer", sa.String(180)), sa.Column("ticket_url", sa.String(500)),
                    sa.Column("image_url", sa.String(500)), sa.Column("is_published", sa.Boolean(), nullable=False),
                    sa.Column("category_id", sa.Integer(), sa.ForeignKey("categories.id"), nullable=False),
                    sa.Column("location_id", sa.Integer(), sa.ForeignKey("locations.id"), nullable=False),
                    sa.Column("created_at", sa.DateTime(timezone=True)), sa.Column("updated_at", sa.DateTime(timezone=True)))


def downgrade():
    op.drop_table("events"); op.drop_table("admin_users"); op.drop_table("locations"); op.drop_table("categories")
