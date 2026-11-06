"""complete milestone2 schema

Revision ID: 0004_complete_milestone2_schema
Revises: 0003_milestone_event_fields
Create Date: 2026-11-05
"""
from alembic import op
import sqlalchemy as sa

revision = "0004_complete_milestone2_schema"
down_revision = "0003_milestone_event_fields"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    insp = sa.inspect(conn)

    # 1. Update categories
    cat_cols = {c["name"] for c in insp.get_columns("categories")}
    with op.batch_alter_table("categories") as batch:
        if "icon" not in cat_cols:
            batch.add_column(sa.Column("icon", sa.String(40), nullable=True))
        if "is_active" not in cat_cols:
            batch.add_column(sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()))

    # 2. Update locations
    loc_cols = {c["name"] for c in insp.get_columns("locations")}
    loc_indexes = {i["name"] for i in insp.get_indexes("locations")}
    with op.batch_alter_table("locations") as batch:
        if "district" not in loc_cols:
            batch.add_column(sa.Column("district", sa.String(120), nullable=True))
        if "is_active" not in loc_cols:
            batch.add_column(sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()))
        if "ix_locations_district" not in loc_indexes:
            batch.create_index("ix_locations_district", ["district"])
        if "ix_locations_city" not in loc_indexes:
            batch.create_index("ix_locations_city", ["city"])

    # 3. Update events
    ev_cols = {c["name"] for c in insp.get_columns("events")}
    ev_indexes = {i["name"] for i in insp.get_indexes("events")}
    with op.batch_alter_table("events") as batch:
        new_cols = [
            ("registration_deadline", sa.DateTime(timezone=True), True, None),
            ("participation_fee", sa.Float(), True, None),
            ("currency", sa.String(10), False, "INR"),
            ("tags", sa.JSON(), False, "[]"),
            ("eligibility", sa.Text(), True, None),
            ("organizer_website", sa.String(500), True, None),
            ("official_website", sa.String(500), True, None),
            ("contact_email", sa.String(320), True, None),
        ]
        for col_name, col_type, is_null, def_val in new_cols:
            if col_name not in ev_cols:
                if def_val is not None:
                    batch.add_column(sa.Column(col_name, col_type, nullable=is_null, server_default=def_val))
                else:
                    batch.add_column(sa.Column(col_name, col_type, nullable=is_null))

        new_indexes = [
            ("ix_events_start_date", ["start_date"]),
            ("ix_events_end_date", ["end_date"]),
            ("ix_events_status", ["status"]),
            ("ix_events_category_id", ["category_id"]),
            ("ix_events_location_id", ["location_id"]),
            ("ix_events_city", ["city"]),
            ("ix_events_district", ["district"]),
            ("ix_events_is_published", ["is_published"]),
        ]
        for idx_name, idx_cols in new_indexes:
            if idx_name not in ev_indexes:
                batch.create_index(idx_name, idx_cols)

    conn.execute(sa.text("""
        UPDATE events SET
            start_date = COALESCE(start_date, starts_at),
            end_date = COALESCE(end_date, ends_at),
            organizer_name = COALESCE(organizer_name, organizer),
            registration_url = COALESCE(registration_url, ticket_url),
            banner_url = COALESCE(banner_url, image_url),
            status = COALESCE(status, CASE WHEN is_published IS TRUE THEN 'published' ELSE 'draft' END),
            currency = COALESCE(currency, 'INR')
    """))


def downgrade():
    conn = op.get_bind()
    insp = sa.inspect(conn)

    ev_indexes = {i["name"] for i in insp.get_indexes("events")}
    ev_cols = {c["name"] for c in insp.get_columns("events")}
    with op.batch_alter_table("events") as batch:
        for idx_name in [
            "ix_events_is_published", "ix_events_district", "ix_events_city",
            "ix_events_location_id", "ix_events_category_id", "ix_events_status",
            "ix_events_end_date", "ix_events_start_date"
        ]:
            if idx_name in ev_indexes:
                batch.drop_index(idx_name)

        for col_name in [
            "contact_email", "official_website", "organizer_website", "eligibility",
            "tags", "currency", "participation_fee", "registration_deadline"
        ]:
            if col_name in ev_cols:
                batch.drop_column(col_name)

    loc_indexes = {i["name"] for i in insp.get_indexes("locations")}
    loc_cols = {c["name"] for c in insp.get_columns("locations")}
    with op.batch_alter_table("locations") as batch:
        if "ix_locations_city" in loc_indexes:
            batch.drop_index("ix_locations_city")
        if "ix_locations_district" in loc_indexes:
            batch.drop_index("ix_locations_district")
        if "is_active" in loc_cols:
            batch.drop_column("is_active")
        if "district" in loc_cols:
            batch.drop_column("district")

    cat_cols = {c["name"] for c in insp.get_columns("categories")}
    with op.batch_alter_table("categories") as batch:
        if "icon" in cat_cols:
            batch.drop_column("icon")
        if "is_active" in cat_cols:
            batch.drop_column("is_active")
