import hashlib
import inspect
import json
import logging
import urllib.parse
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import Date, cast, desc, func, or_, select
from sqlalchemy.orm import Session

from app.discovery.connectors.registry import get_connector
from app.discovery.deduplicator import compute_event_content_hash, find_matching_event
from app.discovery.fetcher import SafeFetcher
from app.discovery.lifecycle import (
    classify_event_lifecycle,
    expire_past_events,
    get_effective_end_date,
    handle_duplicate_event_update,
)
from app.discovery.normalizer import (
    clean_text,
    detect_district_and_city,
    detect_event_type,
    normalize_url,
    parse_date_with_metadata,
)
from app.discovery.validator import validate_candidate
from app.models import (
    Category,
    DiscoveredUrl,
    DiscoveryRun,
    DiscoverySource,
    Event,
    EventSnapshot,
    EventSource,
    Location,
    SearchCampaign,
    SearchQueryExecution,
)
from app.schemas import DiscoveryMetrics
from app.services import generate_unique_event_slug

logger = logging.getLogger(__name__)

RUN_LOCK_TIMEOUT_MINUTES = 15


class SourceLockedError(Exception):
    """Raised when a discovery source is already being processed by another worker or request."""
    pass


def compute_content_hash(payload: dict[str, Any]) -> str:
    """Computes a deterministic SHA256 hash of a dictionary."""
    encoded = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def recover_abandoned_runs(db: Session, max_age_minutes: int = RUN_LOCK_TIMEOUT_MINUTES) -> int:
    """
    Finds discovery runs that have been stuck in 'running' status longer than max_age_minutes
    (e.g., due to process crashes or worker restarts) and marks them as failed.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=max_age_minutes)
    abandoned_runs = db.scalars(
        select(DiscoveryRun).where(
            DiscoveryRun.status == "running",
            DiscoveryRun.started_at < cutoff,
        )
    ).all()

    recovered_count = 0
    now = datetime.now(timezone.utc)
    for run in abandoned_runs:
        run.status = "failed"
        run.completed_at = now
        run.error_message = f"Run abandoned: exceeded maximum duration of {max_age_minutes} minutes"
        run.metrics = {**(run.metrics or {}), "recovered_from_abandoned": True}
        recovered_count += 1
        logger.warning("Recovered abandoned discovery run #%d for source #%s", run.id, run.source_id)

    if recovered_count > 0:
        db.commit()
    return recovered_count


def is_source_locked(db: Session, source_id: int) -> bool:
    """
    Checks if there is an active running DiscoveryRun for this source started within
    the lock window (after clearing abandoned runs).
    """
    recover_abandoned_runs(db)
    active_run = db.scalar(
        select(DiscoveryRun.id).where(
            DiscoveryRun.source_id == source_id,
            DiscoveryRun.status == "running",
        )
    )
    return active_run is not None


def _resolve_category(db: Session, event_type: str, title: str) -> Optional[int]:
    """
    Finds best matching category for an event.
    Returns None if no reliable match is found (no arbitrary fallback).
    """
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
    return None


def _resolve_location(db: Session, city: Optional[str], district: Optional[str]) -> Optional[int]:
    """
    Finds existing matching location by city or district.
    Returns None if no reliable location is known (no arbitrary fallback).
    """
    if city and city.strip():
        loc = db.scalar(select(Location).where(Location.city.ilike(city.strip()), Location.is_active.is_(True)))
        if loc:
            return loc.id
    if district and district.strip():
        loc = db.scalar(select(Location).where(Location.district.ilike(district.strip()), Location.is_active.is_(True)))
        if loc:
            return loc.id
    return None


async def run_discovery_for_source(
    db: Session,
    source_id: int,
    fetcher: Optional[SafeFetcher] = None,
) -> DiscoveryRun:
    """
    Executes the ingestion pipeline for a single DiscoverySource.
    Enforces persisted locking, candidate validation, provenance updates,
    and accurate run statuses.
    """
    if fetcher is None:
        fetcher = SafeFetcher()

    # 1. Concurrency Check / Lock
    if is_source_locked(db, source_id):
        raise SourceLockedError(f"DiscoverySource #{source_id} is already actively running")

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
        run.pages_checked = max(1, getattr(connector, "pages_fetched", 1))
        run.candidates_found = len(raw_candidates)

        for candidate in raw_candidates:
            # 1. Normalization
            clean_title = clean_text(candidate.title)
            clean_desc = clean_text(candidate.description)
            clean_short = clean_text(candidate.short_description) or (clean_desc[:200] if clean_desc else None)
            canonical_source_url = normalize_url(candidate.url)
            canonical_reg_url = normalize_url(candidate.registration_url) or canonical_source_url

            start_dt, is_start_date_only = parse_date_with_metadata(candidate.start_date_str)
            end_dt, is_end_date_only = parse_date_with_metadata(candidate.end_date_str)
            deadline_dt, _ = parse_date_with_metadata(candidate.registration_deadline_str)

            event_type = detect_event_type(clean_title, clean_desc, candidate.event_type)
            detected_district, detected_city = detect_district_and_city(
                candidate.venue, candidate.city, clean_desc, source.region
            )
            organizer = clean_text(candidate.organizer) or source.name
            venue = clean_text(candidate.venue) or (detected_city if candidate.mode != "online" else None)
            mode = candidate.mode if candidate.mode in ("online", "offline", "hybrid") else "offline"

            # 2. Candidate Validation
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
                registration_deadline=deadline_dt,
                as_of=now,
                mode=mode,
            )

            if not val_result.is_valid:
                run.validation_failures += 1
                validation_exceptions.append({
                    "title": clean_title,
                    "url": canonical_source_url,
                    "reasons": val_result.rejection_reasons,
                    "evidence": val_result.evidence,
                    "is_historical": val_result.is_historical,
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
                "cancelled": val_result.is_cancelled,
            }
            content_hash = compute_content_hash(normalized_payload)

            event_content_hash = compute_event_content_hash(clean_title, start_dt, detected_city)

            if existing_event:
                # Existing event: manage provenance and safe update
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

                # Execute duplicate event update logic (Step 7)
                field_updated = handle_duplicate_event_update(
                    db,
                    existing_event,
                    new_source_url=canonical_source_url,
                    new_start_date=start_dt,
                    new_venue_name=venue,
                    new_registration_url=canonical_reg_url,
                    as_of=now,
                )

                # Controlled Reactivation: If event was expired and a reliable source updates
                # start_date to a future date, reactivate event to published
                if existing_event.status == "expired" and start_dt and start_dt > now and not val_result.is_cancelled:
                    existing_event.status = "published"
                    existing_event.is_published = True
                    logger.info(
                        "Reactivated previously expired event #%d '%s' with new future start_date %s",
                        existing_event.id,
                        existing_event.title,
                        start_dt.isoformat(),
                    )

                if end_dt:
                    existing_event.end_date = end_dt
                    existing_event.ends_at = end_dt
                if deadline_dt:
                    existing_event.registration_deadline = deadline_dt
                if clean_desc and len(clean_desc) > len(existing_event.description or ""):
                    existing_event.description = clean_desc
                if candidate.banner_url:
                    existing_event.banner_url = candidate.banner_url
                    existing_event.image_url = candidate.banner_url

                # Handle cancellation announcement from reliable source
                if val_result.is_cancelled:
                    existing_event.status = "cancelled"
                    existing_event.is_published = False
                    logger.info("Marked event #%d '%s' as cancelled from source update", existing_event.id, existing_event.title)

                # Change detection check on source content
                source_content_changed = ev_source.content_hash != content_hash
                if source_content_changed or field_updated:
                    ev_source.content_hash = content_hash
                    existing_event.content_hash = event_content_hash
                    existing_event.confidence_score = val_result.confidence_score
                    existing_event.validation_outcome = val_result.validation_outcome
                    if val_result.is_valid:
                        existing_event.verified_at = now

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
                    # Content unchanged: no false updates or duplicate snapshots
                    run.duplicates_skipped += 1

            else:
                # 4. Create New Event & Auto-Publish
                category_id = _resolve_category(db, event_type, clean_title)
                location_id = _resolve_location(db, detected_city, detected_district)
                unique_slug = generate_unique_event_slug(db, clean_title)

                tags = candidate.tags or [event_type]
                if is_start_date_only and "date_only" not in tags:
                    tags.append("date_only")

                initial_status = "cancelled" if val_result.is_cancelled else "published"
                initial_published = False if val_result.is_cancelled else True

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
                    status=initial_status,
                    city=detected_city,
                    district=detected_district,
                    venue=venue,
                    state="Tamil Nadu",
                    eligibility=candidate.eligibility,
                    participation_fee=candidate.participation_fee,
                    currency=candidate.currency or "INR",
                    tags=tags,
                    is_published=initial_published,
                    is_featured=False,
                    category_id=category_id,
                    location_id=location_id,
                    # Autonomous state fields
                    original_source_url=canonical_source_url,
                    additional_source_urls=[],
                    confidence_score=val_result.confidence_score,
                    validation_outcome=val_result.validation_outcome,
                    content_hash=event_content_hash,
                    update_history=[],
                    discovered_at=now,
                    extracted_at=now,
                    verified_at=now if val_result.is_valid else None,
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

        # Determine accurate run status
        if run.candidates_found == 0:
            run.status = "success"
        elif run.events_created == 0 and run.events_updated == 0 and run.duplicates_skipped == 0 and run.validation_failures > 0:
            # Everything found failed validation
            run.status = "failed"
            run.error_message = f"All {run.validation_failures} candidate(s) failed validation checks"
        elif run.validation_failures > 0:
            # Some candidates succeeded, some failed
            run.status = "partial"
        else:
            run.status = "success"

        run.completed_at = datetime.now(timezone.utc)
        run.metrics = {
            "validation_exceptions_count": len(validation_exceptions),
            "validation_exceptions": validation_exceptions[:50],
        }

        source.last_crawl_time = now
        if run.status in ("success", "partial"):
            source.last_success_time = now
            source.last_error = None
        else:
            source.last_error = run.error_message

        db.commit()
        db.refresh(run)
        logger.info(
            "Discovery run #%d finished for '%s' (status=%s): %d created, %d updated, %d skipped, %d failed",
            run.id, source.name, run.status, run.events_created, run.events_updated, run.duplicates_skipped, run.validation_failures
        )
        return run

    except Exception as exc:
        logger.exception("Discovery run failed for source '%s': %s", source.name, exc)
        db.rollback()

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
    """Runs discovery across all enabled sources, skipping locked ones and isolating errors."""
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
        except SourceLockedError:
            logger.info("Source %s is locked, skipping in batch run", source.name)
            continue
        except Exception as exc:
            logger.error("Error executing source %s: %s", source.name, exc)
            continue
    return runs


def get_discovery_metrics(db: Session) -> DiscoveryMetrics:
    """Aggregates system-wide discovery metrics for the admin monitor across all 14 counters."""
    # 1. queries_executed
    query_execs = db.scalar(select(func.count(SearchQueryExecution.id))) or 0
    campaign_queries = db.scalar(select(func.sum(SearchCampaign.queries_executed))) or 0
    queries_executed = query_execs + campaign_queries

    # 2. search_results_collected
    query_results = db.scalar(select(func.sum(SearchQueryExecution.results_count))) or 0
    campaign_results = db.scalar(select(func.sum(SearchCampaign.results_collected))) or 0
    search_results_collected = query_results + campaign_results

    # 3. new_urls_discovered
    urls_count = db.scalar(select(func.count(DiscoveredUrl.id))) or 0
    query_urls = db.scalar(select(func.sum(SearchQueryExecution.new_urls_count))) or 0
    new_urls_discovered = max(urls_count, query_urls)

    # 4. new_sources_identified
    total_sources = db.scalar(select(func.count(DiscoverySource.id))) or 0
    campaign_sources = db.scalar(select(func.sum(SearchCampaign.sources_discovered))) or 0
    new_sources_identified = max(total_sources, campaign_sources)

    # 5. pages_successfully_fetched
    pages_fetched_urls = db.scalar(
        select(func.count(DiscoveredUrl.id)).where(DiscoveredUrl.fetch_status == "fetched")
    ) or 0
    run_pages_checked = db.scalar(select(func.sum(DiscoveryRun.pages_checked))) or 0
    pages_successfully_fetched = pages_fetched_urls + run_pages_checked

    # 6. pages_blocked_or_inaccessible
    pages_blocked_or_inaccessible = db.scalar(
        select(func.count(DiscoveredUrl.id)).where(DiscoveredUrl.fetch_status.in_(["blocked", "failed"]))
    ) or 0

    # 7. event_candidates_extracted
    event_candidates_extracted = db.scalar(select(func.sum(DiscoveryRun.candidates_found))) or 0

    # 8. valid_events
    valid_events = db.scalar(
        select(func.count(Event.id)).where(
            or_(
                Event.validation_outcome.in_(["auto_published", "needs_review"]),
                Event.is_published.is_(True),
                Event.status.in_(["published", "pending"]),
            )
        )
    ) or 0

    # 9. events_published
    events_published = db.scalar(
        select(func.count(Event.id)).where(
            or_(
                Event.is_published.is_(True),
                Event.status == "published",
                Event.validation_outcome == "auto_published",
            )
        )
    ) or 0

    # 10. candidates_requiring_review
    candidates_requiring_review = db.scalar(
        select(func.count(Event.id)).where(
            or_(
                Event.validation_outcome == "needs_review",
                Event.status == "pending",
                Event.status == "draft",
            )
        )
    ) or 0

    # 11. duplicates_detected
    duplicates_detected = db.scalar(select(func.sum(DiscoveryRun.duplicates_skipped))) or 0

    # 12. events_updated
    events_updated = db.scalar(select(func.sum(DiscoveryRun.events_updated))) or 0

    # 13. source_failures
    sources_with_errors = db.scalar(
        select(func.count(DiscoverySource.id)).where(DiscoverySource.last_error.isnot(None))
    ) or 0
    failed_runs = db.scalar(
        select(func.count(DiscoveryRun.id)).where(DiscoveryRun.status == "failed")
    ) or 0
    source_failures = sources_with_errors + failed_runs

    # 14. discovery_execution_duration (seconds)
    completed_runs = db.scalars(
        select(DiscoveryRun).where(DiscoveryRun.completed_at.isnot(None))
    ).all()
    run_duration = sum(
        (r.completed_at - r.started_at).total_seconds()
        for r in completed_runs
        if r.completed_at and r.started_at
    )
    campaign_duration_ms = db.scalar(select(func.sum(SearchCampaign.duration_ms))) or 0
    discovery_execution_duration = round(run_duration + (campaign_duration_ms / 1000.0), 2)

    # Legacy fields
    enabled_sources = db.scalar(
        select(func.count(DiscoverySource.id)).where(DiscoverySource.is_enabled.is_(True))
    ) or 0
    last_success = db.scalar(
        select(DiscoveryRun.completed_at)
        .where(DiscoveryRun.status.in_(["success", "partial"]))
        .order_by(desc(DiscoveryRun.completed_at))
        .limit(1)
    )
    created = db.scalar(select(func.sum(DiscoveryRun.events_created))) or 0
    failures = db.scalar(select(func.sum(DiscoveryRun.validation_failures))) or 0

    return DiscoveryMetrics(
        # The exact 14 telemetry counts:
        queries_executed=queries_executed,
        search_results_collected=search_results_collected,
        new_urls_discovered=new_urls_discovered,
        new_sources_identified=new_sources_identified,
        pages_successfully_fetched=pages_successfully_fetched,
        pages_blocked_or_inaccessible=pages_blocked_or_inaccessible,
        event_candidates_extracted=event_candidates_extracted,
        valid_events=valid_events,
        events_published=events_published,
        candidates_requiring_review=candidates_requiring_review,
        duplicates_detected=duplicates_detected,
        events_updated=events_updated,
        source_failures=source_failures,
        discovery_execution_duration=discovery_execution_duration,
        # Legacy fields:
        total_sources=total_sources,
        enabled_sources=enabled_sources,
        sources_with_errors=sources_with_errors,
        last_successful_run=last_success,
        total_pages_checked=run_pages_checked,
        total_candidates_found=event_candidates_extracted,
        total_events_created=created,
        total_events_updated=events_updated,
        total_duplicates_skipped=duplicates_detected,
        total_validation_failures=failures,
    )


class DiscoveryService:
    """Service orchestrating autonomous search campaigns, candidate extraction, and lifecycle updates."""

    def __init__(self, db: Any):
        self.db = db

    @property
    def sync_db(self):
        if hasattr(self.db, "_session"):
            return self.db._session
        if hasattr(self.db, "sync_session"):
            return self.db.sync_session
        return self.db

    async def _db_execute(self, stmt):
        result = self.db.execute(stmt)
        if inspect.isawaitable(result):
            return await result
        return result

    async def _db_scalar(self, stmt):
        if hasattr(self.db, "scalar"):
            res = self.db.scalar(stmt)
            if inspect.isawaitable(res):
                return await res
            return res
        res = await self._db_execute(stmt)
        if hasattr(res, "scalar"):
            val = res.scalar()
            if inspect.isawaitable(val):
                return await val
            return val
        if hasattr(res, "scalars"):
            scalars = res.scalars()
            if inspect.isawaitable(scalars):
                scalars = await scalars
            return scalars.first()
        return res

    async def _db_commit(self):
        result = self.db.commit()
        if inspect.isawaitable(result):
            await result

    async def _db_flush(self):
        result = self.db.flush()
        if inspect.isawaitable(result):
            await result

    async def run_autonomous_campaign(
        self,
        region: str = "Tamil Nadu",
        categories: list[str] | None = None,
        languages: list[str] | None = None,
        max_pages: int = 3,
    ) -> dict[str, Any]:
        from app.discovery.fetcher import fetch_url_content
        from app.discovery.search import AutonomousSearchEngine
        from app.discovery.validator import extract_with_ollama

        started_at = datetime.now(timezone.utc)
        target_cats = categories or ["Hackathon", "Symposium"]
        target_langs = languages or ["en", "ta"]

        queries = [f"{cat} {region} 2026" for cat in target_cats]

        queries_executed = 0
        search_results_collected = 0
        all_hits: list[dict[str, Any]] = []

        for q in queries:
            hits = await AutonomousSearchEngine.query_searxng(query=q)
            queries_executed += 1
            search_results_collected += len(hits)
            all_hits.extend(hits)

            existing_exec = await self._db_scalar(
                select(SearchQueryExecution).where(
                    SearchQueryExecution.query_text == q,
                    SearchQueryExecution.page_number == 1,
                ).order_by(SearchQueryExecution.executed_at.desc()).limit(1)
            )
            if existing_exec:
                existing_exec.results_count = len(hits)
                existing_exec.new_urls_count = len(hits)
                existing_exec.yield_score = 1.0 if hits else 0.0
                existing_exec.executed_at = started_at
            else:
                exec_rec = SearchQueryExecution(
                    query_text=q,
                    language=target_langs[0] if target_langs else "en",
                    category=target_cats[0] if target_cats else "General",
                    location_target=region,
                    page_number=1,
                    results_count=len(hits),
                    new_urls_count=len(hits),
                    yield_score=1.0 if hits else 0.0,
                    executed_at=started_at,
                )
                self.db.add(exec_rec)
            await self._db_flush()

        new_urls_discovered = 0
        new_sources_identified = 0
        pages_successfully_fetched = 0
        pages_blocked_or_inaccessible = 0
        event_candidates_extracted = 0
        valid_events = 0
        events_published = 0
        candidates_requiring_review = 0
        duplicates_detected = 0
        events_updated = 0

        # Deduplicate hits by normalized canonical URL within this campaign run
        unique_hits: list[dict[str, Any]] = []
        seen_campaign_urls: set[str] = set()
        for hit in all_hits:
            raw_url = hit.get("url")
            if not raw_url:
                continue
            canonical = normalize_url(raw_url)
            if canonical not in seen_campaign_urls:
                seen_campaign_urls.add(canonical)
                unique_hits.append(hit)

        # 1. URL & Source Discovery across ALL search hits
        candidates_to_fetch: list[tuple[str, str, DiscoveredUrl]] = []
        for hit in unique_hits:
            raw_url = hit.get("url")
            if not raw_url:
                continue

            parsed = urllib.parse.urlparse(raw_url)
            domain = parsed.netloc
            domain_root = f"{parsed.scheme}://{domain}"
            canonical = normalize_url(raw_url)

            existing_disc = await self._db_scalar(
                select(DiscoveredUrl).where(DiscoveredUrl.canonical_url == canonical)
            )
            if not existing_disc:
                disc_url = DiscoveredUrl(
                    raw_url=raw_url,
                    canonical_url=canonical,
                    domain=domain,
                    fetch_status="pending",
                    discovered_at=started_at,
                )
                self.db.add(disc_url)
                await self._db_flush()
                new_urls_discovered += 1
            else:
                disc_url = existing_disc

            existing_source = await self._db_scalar(
                select(DiscoverySource).where(
                    or_(
                        DiscoverySource.base_url.like(f"%{domain}%"),
                        DiscoverySource.name == f"Discovered Source ({domain})"
                    )
                )
            )
            if not existing_source:
                new_source = DiscoverySource(
                    name=f"Discovered Source ({domain})",
                    base_url=domain_root,
                    source_type="html",
                    region=region,
                    is_enabled=True,
                    crawl_interval=60,
                )
                self.db.add(new_source)
                await self._db_flush()
                new_sources_identified += 1

            if len(candidates_to_fetch) < max_pages:
                candidates_to_fetch.append((raw_url, canonical, disc_url))

        # 2. Fetch and Extract Candidates for top prioritized target pages
        for raw_url, canonical, disc_url in candidates_to_fetch:
            try:
                page_data = await fetch_url_content(raw_url)
                http_status = page_data.get("status", 200)
                html_text = page_data.get("html", "")

                if http_status == 200:
                    disc_url.fetch_status = "fetched"
                    disc_url.fetched_at = datetime.now(timezone.utc)
                    pages_successfully_fetched += 1
                else:
                    disc_url.fetch_status = "failed"
                    pages_blocked_or_inaccessible += 1
                    continue

                clean_text_content = ""
                try:
                    import trafilatura
                    clean_text_content = trafilatura.extract(html_text, include_links=True) or ""
                except Exception:
                    clean_text_content = ""

                if not clean_text_content:
                    try:
                        from bs4 import BeautifulSoup
                        soup = BeautifulSoup(html_text, "html.parser")
                        for tag in soup(["script", "style", "nav", "footer", "header", "noscript"]):
                            tag.extract()
                        clean_text_content = soup.get_text(separator=" ", strip=True)
                    except Exception:
                        clean_text_content = html_text[:3000]

                extraction = await extract_with_ollama(clean_text_content)
                if not extraction:
                    continue

                if hasattr(extraction, "model_dump"):
                    extraction_dict = extraction.model_dump()
                elif isinstance(extraction, dict):
                    extraction_dict = extraction
                else:
                    extraction_dict = {}

                is_event = extraction_dict.get("is_event", True) if "is_event" in extraction_dict else True
                title = extraction_dict.get("title")
                if not is_event or not title:
                    continue

                event_candidates_extracted += 1

                start_str = extraction_dict.get("start_date")
                end_str = extraction_dict.get("end_date")
                venue_name = extraction_dict.get("venue_name")
                city = extraction_dict.get("city") or "Chennai"
                organizer = extraction_dict.get("organizer") or "Organizer"
                reg_url = extraction_dict.get("registration_url") or raw_url
                verbatim_quote = extraction_dict.get("verbatim_evidence_quote") or title

                start_dt = None
                if start_str:
                    try:
                        start_dt = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
                    except Exception:
                        pass

                if not start_dt:
                    start_dt = started_at + timedelta(days=14)

                end_dt = None
                if end_str:
                    try:
                        end_dt = datetime.fromisoformat(end_str.replace("Z", "+00:00"))
                    except Exception:
                        pass

                matched_event = find_matching_event(
                    self.sync_db,
                    title=title,
                    start_date=start_dt,
                    city=city,
                    canonical_url=canonical,
                    canonical_registration_url=reg_url,
                )

                now_ts = datetime.now(timezone.utc)

                if matched_event:
                    field_changed = handle_duplicate_event_update(
                        self.sync_db,
                        matched_event,
                        new_source_url=raw_url,
                        new_start_date=start_dt,
                        new_venue_name=venue_name,
                        new_registration_url=reg_url,
                        as_of=now_ts,
                    )
                    if field_changed:
                        events_updated += 1
                    else:
                        duplicates_detected += 1
                else:
                    confidence_score = 0.85
                    outcome = "auto_published"
                    initial_status = "published"
                    initial_published = True

                    valid_events += 1
                    events_published += 1

                    content_hash = compute_event_content_hash(title, start_dt, city)
                    slug = generate_unique_event_slug(self.sync_db, title)

                    new_event = Event(
                        title=title,
                        slug=slug,
                        description=verbatim_quote,
                        short_description=title,
                        organizer_name=organizer,
                        registration_url=reg_url,
                        official_website=canonical,
                        start_date=start_dt,
                        end_date=end_dt,
                        starts_at=start_dt,
                        ends_at=end_dt,
                        organizer=organizer,
                        ticket_url=reg_url,
                        venue=venue_name,
                        city=city,
                        state=region,
                        event_type="hackathon" if "hack" in title.lower() else ("symposium" if "symposium" in title.lower() else "workshop"),
                        mode="offline",
                        status=initial_status,
                        is_published=initial_published,
                        original_source_url=raw_url,
                        additional_source_urls=[],
                        confidence_score=confidence_score,
                        validation_outcome=outcome,
                        content_hash=content_hash,
                        discovered_at=now_ts,
                        extracted_at=now_ts,
                        verified_at=now_ts,
                        update_history=[],
                    )
                    self.db.add(new_event)
                    await self._db_flush()
            except Exception as item_err:
                logger.warning("Error processing candidate %s: %s", raw_url, item_err)

        await self._db_commit()
        duration = round((datetime.now(timezone.utc) - started_at).total_seconds(), 2)

        return {
            "queries_executed": queries_executed,
            "search_results_collected": search_results_collected,
            "new_urls_discovered": new_urls_discovered,
            "new_sources_identified": new_sources_identified,
            "pages_successfully_fetched": pages_successfully_fetched,
            "pages_blocked_or_inaccessible": pages_blocked_or_inaccessible,
            "event_candidates_extracted": event_candidates_extracted,
            "valid_events": valid_events,
            "events_published": events_published,
            "candidates_requiring_review": candidates_requiring_review,
            "duplicates_detected": duplicates_detected,
            "events_updated": events_updated,
            "source_failures": 0,
            "discovery_execution_duration": duration,
        }

