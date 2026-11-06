import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.discovery.connectors.registry import get_connector
from app.discovery.deduplicator import find_matching_event
from app.discovery.fetcher import SafeFetcher
from app.discovery.normalizer import (
    clean_text,
    detect_district_and_city,
    detect_event_type,
    normalize_url,
    parse_and_localize_date,
)
from app.discovery.validator import validate_candidate
from app.models import (
    Category,
    DiscoveryRun,
    DiscoverySource,
    Event,
    EventSnapshot,
    EventSource,
    Location,
)
from app.schemas import DiscoveryMetrics
from app.services import generate_unique_event_slug

logger = logging.getLogger(__name__)


def compute_content_hash(payload: dict[str, Any]) -> str:
    """Computes a deterministic SHA256 hash of a dictionary."""
    encoded = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _resolve_category(db: Session, event_type: str, title: str) -> Optional[int]:
    """Finds best matching category for an event."""
    slug_keywords = {
        "hackathon": "technology-hackathons",
        "competition": "technology-hackathons",
        "open_source": "technology-hackathons",
        "workshop": "workshops-heritage",
        "conference": "technology-hackathons",
        "symposium": "technology-hackathons",
        "startup": "business-startups",
    }
    target_slug = slug_keywords.get(event_type)
    if target_slug:
        cat = db.scalar(select(Category).where(Category.slug == target_slug, Category.is_active.is_(True)))
        if cat:
            return cat.id

    first_cat = db.scalar(select(Category).where(Category.is_active.is_(True)).order_by(Category.id))
    return first_cat.id if first_cat else None


def _resolve_location(db: Session, city: Optional[str], district: Optional[str]) -> Optional[int]:
    """Finds existing matching location by city or district, falling back to default active location."""
    if city:
        loc = db.scalar(select(Location).where(Location.city.ilike(city), Location.is_active.is_(True)))
        if loc:
            return loc.id
    if district:
        loc = db.scalar(select(Location).where(Location.district.ilike(district), Location.is_active.is_(True)))
        if loc:
            return loc.id
    fallback_loc = db.scalar(select(Location).where(Location.is_active.is_(True)).order_by(Location.id))
    return fallback_loc.id if fallback_loc else None


async def run_discovery_for_source(
    db: Session,
    source_id: int,
    fetcher: Optional[SafeFetcher] = None,
) -> DiscoveryRun:
    """
    Executes the ingestion pipeline for a single DiscoverySource.
    Isolates source errors so calling workflows continue cleanly.
    """
    if fetcher is None:
        fetcher = SafeFetcher()

    source = db.get(DiscoverySource, source_id)
    if not source:
        raise ValueError(f"DiscoverySource with id {source_id} does not exist")

    now = datetime.now(timezone.utc)
    run = DiscoveryRun(
        source_id=source.id,
        started_at=now,
        status="running",
        pages_checked=0,
        candidates_found=0,
        events_created=0,
        events_updated=0,
        duplicates_skipped=0,
        validation_failures=0,
        metrics={},
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    validation_exceptions: list[dict[str, Any]] = []

    try:
        connector = get_connector(source.source_type)
        raw_candidates = await connector.extract_candidates(source, fetcher)
        run.pages_checked = 1
        run.candidates_found = len(raw_candidates)

        for candidate in raw_candidates:
            # 1. Normalization
            clean_title = clean_text(candidate.title)
            clean_desc = clean_text(candidate.description)
            clean_short = clean_text(candidate.short_description) or (clean_desc[:200] if clean_desc else None)
            canonical_source_url = normalize_url(candidate.url)
            canonical_reg_url = normalize_url(candidate.registration_url) or canonical_source_url

            start_dt = parse_and_localize_date(candidate.start_date_str)
            end_dt = parse_and_localize_date(candidate.end_date_str)
            deadline_dt = parse_and_localize_date(candidate.registration_deadline_str)

            event_type = detect_event_type(clean_title, clean_desc, candidate.event_type)
            detected_district, detected_city = detect_district_and_city(
                candidate.venue, candidate.city or source.region, clean_desc
            )
            organizer = clean_text(candidate.organizer) or source.name
            venue = clean_text(candidate.venue) or (detected_city if candidate.mode != "online" else None)
            mode = candidate.mode if candidate.mode in ("online", "offline", "hybrid") else "offline"

            # 2. Validation
            val_result = validate_candidate(
                title=clean_title,
                description=clean_desc,
                start_date=start_dt,
                end_date=end_dt,
                registration_url=canonical_reg_url,
                organizer_name=organizer,
                source_name=source.name,
                venue=venue,
                city=detected_city,
            )

            if not val_result.is_valid:
                run.validation_failures += 1
                validation_exceptions.append({
                    "title": clean_title,
                    "url": canonical_source_url,
                    "reasons": val_result.rejection_reasons,
                    "evidence": val_result.evidence,
                })
                continue

            # 3. Deduplication Check
            existing_event = find_matching_event(
                db,
                source_id=source.id,
                canonical_url=canonical_source_url,
                canonical_registration_url=canonical_reg_url,
                external_event_id=candidate.external_id,
                title=clean_title,
                start_date=start_dt,  # type: ignore[arg-type]
                organizer_name=organizer,
                city=detected_city,
            )

            normalized_payload = {
                "title": clean_title,
                "description": clean_desc,
                "start_date": start_dt.isoformat() if start_dt else None,
                "end_date": end_dt.isoformat() if end_dt else None,
                "registration_deadline": deadline_dt.isoformat() if deadline_dt else None,
                "registration_url": canonical_reg_url,
                "venue": venue,
                "organizer": organizer,
                "fee": candidate.participation_fee,
            }
            content_hash = compute_content_hash(normalized_payload)

            if existing_event:
                # Event already exists in database
                ev_source = db.scalar(
                    select(EventSource).where(
                        EventSource.event_id == existing_event.id,
                        EventSource.source_id == source.id,
                    )
                )

                if not ev_source:
                    # Link new source to existing event
                    ev_source = EventSource(
                        event_id=existing_event.id,
                        source_id=source.id,
                        external_event_id=candidate.external_id,
                        source_event_url=canonical_source_url,
                        canonical_url=canonical_source_url,
                        content_hash=content_hash,
                        first_seen=now,
                        last_seen=now,
                        last_checked=now,
                    )
                    db.add(ev_source)
                    db.flush()
                else:
                    ev_source.last_seen = now
                    ev_source.last_checked = now

                # Change detection
                if ev_source.content_hash != content_hash:
                    # Content updated from source
                    ev_source.content_hash = content_hash
                    # Safely update non-conflicting fields
                    if start_dt:
                        existing_event.start_date = start_dt
                        existing_event.starts_at = start_dt
                    if end_dt:
                        existing_event.end_date = end_dt
                        existing_event.ends_at = end_dt
                    if deadline_dt:
                        existing_event.registration_deadline = deadline_dt
                    if canonical_reg_url:
                        existing_event.registration_url = canonical_reg_url
                        existing_event.ticket_url = canonical_reg_url
                    if venue:
                        existing_event.venue = venue
                    if candidate.banner_url:
                        existing_event.banner_url = candidate.banner_url
                        existing_event.image_url = candidate.banner_url

                    # Add snapshot
                    snapshot = EventSnapshot(
                        event_source_id=ev_source.id,
                        raw_payload=candidate.raw_payload,
                        content_hash=content_hash,
                        created_at=now,
                    )
                    db.add(snapshot)
                    run.events_updated += 1
                else:
                    run.duplicates_skipped += 1

            else:
                # 4. Create New Event & Auto-Publish
                category_id = _resolve_category(db, event_type, clean_title)
                location_id = _resolve_location(db, detected_city, detected_district)
                unique_slug = generate_unique_event_slug(db, clean_title)

                new_event = Event(
                    title=clean_title,
                    slug=unique_slug,
                    short_description=clean_short,
                    description=clean_desc,
                    start_date=start_dt,  # type: ignore[arg-type]
                    end_date=end_dt,
                    registration_deadline=deadline_dt,
                    organizer_name=organizer,
                    organizer_website=candidate.organizer_website,
                    registration_url=canonical_reg_url,
                    official_website=canonical_source_url,
                    banner_url=candidate.banner_url,
                    contact_email=candidate.contact_email,
                    event_type=event_type,
                    mode=mode,
                    status="published",
                    city=detected_city,
                    district=detected_district,
                    venue=venue,
                    state="Tamil Nadu",
                    eligibility=candidate.eligibility,
                    participation_fee=candidate.participation_fee,
                    currency=candidate.currency or "INR",
                    tags=candidate.tags or [event_type],
                    is_published=True,
                    is_featured=False,
                    category_id=category_id,
                    location_id=location_id,
                    # Legacy fields
                    starts_at=start_dt,
                    ends_at=end_dt,
                    organizer=organizer,
                    ticket_url=canonical_reg_url,
                    image_url=candidate.banner_url,
                )
                db.add(new_event)
                db.flush()

                # Create EventSource link
                ev_source = EventSource(
                    event_id=new_event.id,
                    source_id=source.id,
                    external_event_id=candidate.external_id,
                    source_event_url=canonical_source_url,
                    canonical_url=canonical_source_url,
                    content_hash=content_hash,
                    first_seen=now,
                    last_seen=now,
                    last_checked=now,
                )
                db.add(ev_source)
                db.flush()

                # Create EventSnapshot
                snapshot = EventSnapshot(
                    event_source_id=ev_source.id,
                    raw_payload=candidate.raw_payload,
                    content_hash=content_hash,
                    created_at=now,
                )
                db.add(snapshot)
                run.events_created += 1

        run.status = "success"
        run.completed_at = datetime.now(timezone.utc)
        run.metrics = {
            "validation_exceptions_count": len(validation_exceptions),
            "validation_exceptions": validation_exceptions[:25],  # store top 25
        }

        source.last_crawl_time = now
        source.last_success_time = now
        source.last_error = None

        db.commit()
        db.refresh(run)
        logger.info(
            "Discovery run completed for '%s': %d created, %d updated, %d skipped, %d failed validation",
            source.name, run.events_created, run.events_updated, run.duplicates_skipped, run.validation_failures
        )
        return run

    except Exception as exc:
        logger.exception("Discovery run failed for source '%s': %s", source.name, exc)
        db.rollback()

        # Record failure state
        source.last_crawl_time = now
        source.last_error = str(exc)

        run.status = "failed"
        run.completed_at = datetime.now(timezone.utc)
        run.error_message = str(exc)
        run.metrics = {"error": str(exc), "validation_exceptions": validation_exceptions}

        db.add(source)
        db.add(run)
        db.commit()
        db.refresh(run)
        return run


async def run_all_enabled_sources(
    db: Session,
    fetcher: Optional[SafeFetcher] = None,
) -> list[DiscoveryRun]:
    """Runs discovery sequentially across all enabled sources, isolating errors."""
    if fetcher is None:
        fetcher = SafeFetcher()

    sources = db.scalars(
        select(DiscoverySource)
        .where(DiscoverySource.is_enabled.is_(True))
        .order_by(DiscoverySource.id)
    ).all()

    runs: list[DiscoveryRun] = []
    for source in sources:
        try:
            run = await run_discovery_for_source(db, source.id, fetcher)
            runs.append(run)
        except Exception as exc:
            logger.error("Error invoking source %s: %s", source.name, exc)
            continue
    return runs


def expire_past_events(db: Session) -> int:
    """Marks events as expired when their end_date (or start_date) has passed."""
    now = datetime.now(timezone.utc)
    effective_end = func.coalesce(Event.end_date, Event.start_date)

    past_published = db.scalars(
        select(Event).where(
            Event.status == "published",
            effective_end < now,
        )
    ).all()

    expired_count = 0
    for event in past_published:
        event.status = "expired"
        event.is_published = False
        expired_count += 1

    if expired_count > 0:
        db.commit()
        logger.info("Expired %d past events", expired_count)
    return expired_count


def get_discovery_metrics(db: Session) -> DiscoveryMetrics:
    """Aggregates system-wide discovery metrics for the admin monitor."""
    total_sources = db.scalar(select(func.count(DiscoverySource.id))) or 0
    enabled_sources = db.scalar(
        select(func.count(DiscoverySource.id)).where(DiscoverySource.is_enabled.is_(True))
    ) or 0
    sources_with_errors = db.scalar(
        select(func.count(DiscoverySource.id)).where(DiscoverySource.last_error.isnot(None))
    ) or 0

    last_success = db.scalar(
        select(DiscoveryRun.completed_at)
        .where(DiscoveryRun.status == "success")
        .order_by(desc(DiscoveryRun.completed_at))
        .limit(1)
    )

    pages = db.scalar(select(func.sum(DiscoveryRun.pages_checked))) or 0
    candidates = db.scalar(select(func.sum(DiscoveryRun.candidates_found))) or 0
    created = db.scalar(select(func.sum(DiscoveryRun.events_created))) or 0
    updated = db.scalar(select(func.sum(DiscoveryRun.events_updated))) or 0
    skipped = db.scalar(select(func.sum(DiscoveryRun.duplicates_skipped))) or 0
    failures = db.scalar(select(func.sum(DiscoveryRun.validation_failures))) or 0

    return DiscoveryMetrics(
        total_sources=total_sources,
        enabled_sources=enabled_sources,
        sources_with_errors=sources_with_errors,
        last_successful_run=last_success,
        total_pages_checked=pages,
        total_candidates_found=candidates,
        total_events_created=created,
        total_events_updated=updated,
        total_duplicates_skipped=skipped,
        total_validation_failures=failures,
    )
