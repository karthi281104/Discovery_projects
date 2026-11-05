from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    slug: Mapped[str] = mapped_column(String(140), unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    icon: Mapped[str | None] = mapped_column(String(40), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)

    events: Mapped[list["Event"]] = relationship(back_populates="category")


class Location(Base):
    __tablename__ = "locations"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(180), index=True)
    city: Mapped[str] = mapped_column(String(120), index=True)
    district: Mapped[str | None] = mapped_column(String(120), index=True, nullable=True)
    state: Mapped[str] = mapped_column(String(120), default="Tamil Nadu")
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    events: Mapped[list["Event"]] = relationship(back_populates="location")


class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(240), index=True, nullable=False)
    slug: Mapped[str] = mapped_column(String(280), unique=True, index=True, nullable=False)
    short_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    start_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    end_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True, nullable=True)
    registration_deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    organizer_name: Mapped[str] = mapped_column(String(180), nullable=False)
    organizer_website: Mapped[str | None] = mapped_column(String(500), nullable=True)
    registration_url: Mapped[str] = mapped_column(String(500), nullable=False)
    official_website: Mapped[str | None] = mapped_column(String(500), nullable=True)
    banner_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    contact_email: Mapped[str | None] = mapped_column(String(320), nullable=True)

    event_type: Mapped[str] = mapped_column(String(40), default="other", index=True)
    mode: Mapped[str] = mapped_column(String(20), default="offline", index=True)
    status: Mapped[str] = mapped_column(String(20), default="draft", index=True)
    city: Mapped[str | None] = mapped_column(String(120), index=True, nullable=True)
    district: Mapped[str | None] = mapped_column(String(120), index=True, nullable=True)
    venue: Mapped[str | None] = mapped_column(String(240), nullable=True)
    state: Mapped[str] = mapped_column(String(120), default="Tamil Nadu")
    eligibility: Mapped[str | None] = mapped_column(Text, nullable=True)
    participation_fee: Mapped[float | None] = mapped_column(Float, nullable=True)
    currency: Mapped[str] = mapped_column(String(10), default="INR")
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)

    is_published: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    is_featured: Mapped[bool] = mapped_column(Boolean, default=False, index=True)

    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id", ondelete="SET NULL"), nullable=True, index=True)
    location_id: Mapped[int | None] = mapped_column(ForeignKey("locations.id", ondelete="SET NULL"), nullable=True, index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Legacy fields for backward compatibility with 0001 initial schema
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    organizer: Mapped[str | None] = mapped_column(String(180), nullable=True)
    ticket_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    category: Mapped[Category | None] = relationship(back_populates="events")
    location: Mapped[Location | None] = relationship(back_populates="events")


class AdminUser(Base):
    __tablename__ = "admin_users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(256))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
