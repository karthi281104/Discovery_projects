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
    is_verified_venue: Mapped[bool] = mapped_column(Boolean, default=False)

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
    sources: Mapped[list["EventSource"]] = relationship(back_populates="event", cascade="all, delete-orphan")


class AdminUser(Base):
    __tablename__ = "admin_users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(256))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ==========================================
# Milestone 3: Automated Discovery Models
# ==========================================

class DiscoverySource(Base):
    __tablename__ = "discovery_sources"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160), unique=True, index=True, nullable=False)
    base_url: Mapped[str] = mapped_column(String(500), nullable=False)
    source_type: Mapped[str] = mapped_column(String(40), index=True, nullable=False)  # "rss", "jsonld", "html", "api"
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    region: Mapped[str] = mapped_column(String(120), default="Tamil Nadu")
    crawl_interval: Mapped[int] = mapped_column(default=60)  # minutes
    request_config: Mapped[dict] = mapped_column(JSON, default=dict)

    last_crawl_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_success_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    runs: Mapped[list["DiscoveryRun"]] = relationship(back_populates="source", cascade="all, delete-orphan")
    event_sources: Mapped[list["EventSource"]] = relationship(back_populates="source", cascade="all, delete-orphan")


class DiscoveryRun(Base):
    __tablename__ = "discovery_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int | None] = mapped_column(ForeignKey("discovery_sources.id", ondelete="CASCADE"), index=True, nullable=True)

    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="running", index=True)  # "running", "success", "failed", "partial"

    pages_checked: Mapped[int] = mapped_column(default=0)
    candidates_found: Mapped[int] = mapped_column(default=0)
    events_created: Mapped[int] = mapped_column(default=0)
    events_updated: Mapped[int] = mapped_column(default=0)
    duplicates_skipped: Mapped[int] = mapped_column(default=0)
    validation_failures: Mapped[int] = mapped_column(default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    metrics: Mapped[dict] = mapped_column(JSON, default=dict)

    source: Mapped[DiscoverySource | None] = relationship(back_populates="runs")


class EventSource(Base):
    __tablename__ = "event_sources"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), index=True, nullable=False)
    source_id: Mapped[int] = mapped_column(ForeignKey("discovery_sources.id", ondelete="CASCADE"), index=True, nullable=False)

    external_event_id: Mapped[str | None] = mapped_column(String(250), index=True, nullable=True)
    source_event_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    canonical_url: Mapped[str] = mapped_column(String(1000), index=True, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_checked: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    event: Mapped[Event] = relationship(back_populates="sources")
    source: Mapped[DiscoverySource] = relationship(back_populates="event_sources")
    snapshots: Mapped[list["EventSnapshot"]] = relationship(back_populates="event_source", cascade="all, delete-orphan")


class EventSnapshot(Base):
    __tablename__ = "event_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_source_id: Mapped[int] = mapped_column(ForeignKey("event_sources.id", ondelete="CASCADE"), index=True, nullable=False)

    raw_payload: Mapped[dict] = mapped_column(JSON, default=dict)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    event_source: Mapped[EventSource] = relationship(back_populates="snapshots")


class SearchCampaign(Base):
    __tablename__ = "search_campaigns"

    id: Mapped[int] = mapped_column(primary_key=True)
    region: Mapped[str] = mapped_column(String(120), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="running", index=True)
    queries_executed: Mapped[int] = mapped_column(default=0)
    results_collected: Mapped[int] = mapped_column(default=0)
    sources_discovered: Mapped[int] = mapped_column(default=0)
    duration_ms: Mapped[int] = mapped_column(default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    results: Mapped[list["SearchResult"]] = relationship(
        back_populates="campaign", cascade="all, delete-orphan"
    )


class SearchResult(Base):
    __tablename__ = "search_results"

    id: Mapped[int] = mapped_column(primary_key=True)
    campaign_id: Mapped[int] = mapped_column(
        ForeignKey("search_campaigns.id", ondelete="CASCADE"), index=True
    )
    query: Mapped[str] = mapped_column(String(500), index=True)
    url: Mapped[str] = mapped_column(String(1000), index=True)
    title: Mapped[str] = mapped_column(String(500))
    snippet: Mapped[str] = mapped_column(Text, default="")
    relevance_score: Mapped[float] = mapped_column(Float, default=0.0)
    discovered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    campaign: Mapped[SearchCampaign] = relationship(back_populates="results")
