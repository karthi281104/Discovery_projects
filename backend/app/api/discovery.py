from typing import Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.core.security import get_current_admin
from app.db.dependencies import get_db
from app.discovery.fetcher import SafeFetcher
from app.discovery.lifecycle import (
    compute_database_diagnostics,
    reconcile_event_lifecycle,
)
from app.discovery.service import (
    SourceLockedError,
    get_discovery_metrics,
    is_source_locked,
    run_all_enabled_sources,
    run_discovery_for_source,
)
from app.models import AdminUser, DiscoveryRun, DiscoverySource, Event, EventSource, SearchCampaign
from app.schemas import (
    DiscoveryCandidateRead,
    DiscoveryMetrics,
    DiscoveryRunList,
    DiscoveryRunRead,
    DiscoverySourceCreate,
    DiscoverySourceList,
    DiscoverySourceRead,
    DiscoverySourceUpdate,
    EventRead,
    EventSourceRead,
)
from app.discovery.search import run_search_campaign

router = APIRouter(prefix="/discovery", tags=["admin-discovery"])


def auth(admin: AdminUser = Depends(get_current_admin)) -> AdminUser:
    return admin


# ==========================================
# Sources Management
# ==========================================

@router.get("/sources", response_model=DiscoverySourceList)
def list_sources(
    enabled_only: bool = False,
    db: Session = Depends(get_db),
    _: AdminUser = Depends(auth),
):
    query = select(DiscoverySource).order_by(DiscoverySource.id)
    if enabled_only:
        query = query.where(DiscoverySource.is_enabled.is_(True))
    items = list(db.scalars(query).all())
    return DiscoverySourceList(items=items, total=len(items))


@router.post("/sources", response_model=DiscoverySourceRead, status_code=201)
def create_source(
    data: DiscoverySourceCreate,
    db: Session = Depends(get_db),
    _: AdminUser = Depends(auth),
):
    existing = db.scalar(select(DiscoverySource).where(DiscoverySource.name == data.name))
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Source with name '{data.name}' already exists")

    source = DiscoverySource(**data.model_dump())
    db.add(source)
    db.commit()
    db.refresh(source)
    return source


@router.put("/sources/{source_id}", response_model=DiscoverySourceRead)
def update_source(
    source_id: int,
    data: DiscoverySourceUpdate,
    db: Session = Depends(get_db),
    _: AdminUser = Depends(auth),
):
    source = db.get(DiscoverySource, source_id)
    if not source:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Discovery source not found")

    values = data.model_dump(exclude_unset=True)
    if "name" in values and values["name"] != source.name:
        conflict = db.scalar(
            select(DiscoverySource).where(
                DiscoverySource.name == values["name"],
                DiscoverySource.id != source_id,
            )
        )
        if conflict:
            raise HTTPException(status.HTTP_409_CONFLICT, f"Source with name '{values['name']}' already exists")

    for k, v in values.items():
        setattr(source, k, v)

    db.commit()
    db.refresh(source)
    return source


@router.patch("/sources/{source_id}/toggle", response_model=DiscoverySourceRead)
def toggle_source(
    source_id: int,
    db: Session = Depends(get_db),
    _: AdminUser = Depends(auth),
):
    source = db.get(DiscoverySource, source_id)
    if not source:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Discovery source not found")

    source.is_enabled = not source.is_enabled
    db.commit()
    db.refresh(source)
    return source


@router.delete("/sources/{source_id}", status_code=204)
def delete_source(
    source_id: int,
    db: Session = Depends(get_db),
    _: AdminUser = Depends(auth),
):
    source = db.get(DiscoverySource, source_id)
    if not source:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Discovery source not found")
    db.delete(source)
    db.commit()


# ==========================================
# Discovery Runs & Execution
# ==========================================

@router.get("/runs", response_model=DiscoveryRunList)
def list_runs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    source_id: Optional[int] = None,
    status_filter: Optional[str] = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
    _: AdminUser = Depends(auth),
):
    query = select(DiscoveryRun)
    if source_id:
        query = query.where(DiscoveryRun.source_id == source_id)
    if status_filter:
        query = query.where(DiscoveryRun.status == status_filter)

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    offset = (page - 1) * page_size
    items = list(
        db.scalars(
            query.order_by(desc(DiscoveryRun.started_at)).offset(offset).limit(page_size)
        ).all()
    )

    read_items: list[DiscoveryRunRead] = []
    for run in items:
        source_name = run.source.name if run.source else None
        read_items.append(
            DiscoveryRunRead(
                id=run.id,
                source_id=run.source_id,
                source_name=source_name,
                started_at=run.started_at,
                completed_at=run.completed_at,
                status=run.status,
                pages_checked=run.pages_checked,
                candidates_found=run.candidates_found,
                events_created=run.events_created,
                events_updated=run.events_updated,
                duplicates_skipped=run.duplicates_skipped,
                validation_failures=run.validation_failures,
                error_message=run.error_message,
                metrics=run.metrics or {},
            )
        )

    pages = (total + page_size - 1) // page_size if total > 0 else 1
    return DiscoveryRunList(
        items=read_items,
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.get("/runs/{run_id}", response_model=DiscoveryRunRead)
def get_run(
    run_id: int,
    db: Session = Depends(get_db),
    _: AdminUser = Depends(auth),
):
    run = db.get(DiscoveryRun, run_id)
    if not run:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Discovery run not found")
    source_name = run.source.name if run.source else None
    return DiscoveryRunRead(
        id=run.id,
        source_id=run.source_id,
        source_name=source_name,
        started_at=run.started_at,
        completed_at=run.completed_at,
        status=run.status,
        pages_checked=run.pages_checked,
        candidates_found=run.candidates_found,
        events_created=run.events_created,
        events_updated=run.events_updated,
        duplicates_skipped=run.duplicates_skipped,
        validation_failures=run.validation_failures,
        error_message=run.error_message,
        metrics=run.metrics or {},
    )


@router.post("/run", response_model=list[DiscoveryRunRead])
async def trigger_all_sources(
    db: Session = Depends(get_db),
    _: AdminUser = Depends(auth),
):
    fetcher = SafeFetcher()
    runs = await run_all_enabled_sources(db, fetcher)
    return [
        DiscoveryRunRead(
            id=r.id,
            source_id=r.source_id,
            source_name=r.source.name if r.source else None,
            started_at=r.started_at,
            completed_at=r.completed_at,
            status=r.status,
            pages_checked=r.pages_checked,
            candidates_found=r.candidates_found,
            events_created=r.events_created,
            events_updated=r.events_updated,
            duplicates_skipped=r.duplicates_skipped,
            validation_failures=r.validation_failures,
            error_message=r.error_message,
            metrics=r.metrics or {},
        )
        for r in runs
    ]


@router.post("/search", status_code=201)
async def trigger_search_campaign(
    db: Session = Depends(get_db),
    _: AdminUser = Depends(auth),
) -> dict[str, object]:
    """Run a configured SearXNG campaign and persist discovered sources/results."""
    try:
        campaign = await run_search_campaign(db)
    except RuntimeError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
    return {
        "id": campaign.id,
        "status": campaign.status,
        "region": campaign.region,
        "queries_executed": campaign.queries_executed,
        "results_collected": campaign.results_collected,
        "sources_discovered": campaign.sources_discovered,
        "duration_ms": campaign.duration_ms,
        "error_message": campaign.error_message,
    }


@router.get("/search/campaigns")
def list_search_campaigns(
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: AdminUser = Depends(auth),
) -> list[dict[str, object]]:
    campaigns = db.scalars(
        select(SearchCampaign).order_by(desc(SearchCampaign.started_at)).limit(limit)
    ).all()
    return [
        {
            "id": campaign.id,
            "status": campaign.status,
            "region": campaign.region,
            "started_at": campaign.started_at,
            "completed_at": campaign.completed_at,
            "queries_executed": campaign.queries_executed,
            "results_collected": campaign.results_collected,
            "sources_discovered": campaign.sources_discovered,
            "duration_ms": campaign.duration_ms,
            "error_message": campaign.error_message,
        }
        for campaign in campaigns
    ]


@router.post("/run/{source_id}", response_model=DiscoveryRunRead)
async def trigger_source(
    source_id: int,
    db: Session = Depends(get_db),
    _: AdminUser = Depends(auth),
):
    if is_source_locked(db, source_id):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Discovery source #{source_id} is already in progress in another process",
        )

    source = db.get(DiscoverySource, source_id)
    if not source:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Discovery source not found")

    fetcher = SafeFetcher()
    try:
        run = await run_discovery_for_source(db, source_id, fetcher)
    except SourceLockedError:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Discovery source #{source_id} is already running",
        )

    return DiscoveryRunRead(
        id=run.id,
        source_id=run.source_id,
        source_name=source.name,
        started_at=run.started_at,
        completed_at=run.completed_at,
        status=run.status,
        pages_checked=run.pages_checked,
        candidates_found=run.candidates_found,
        events_created=run.events_created,
        events_updated=run.events_updated,
        duplicates_skipped=run.duplicates_skipped,
        validation_failures=run.validation_failures,
        error_message=run.error_message,
        metrics=run.metrics or {},
    )


# ==========================================
# Metrics, Candidates & Attribution
# ==========================================

@router.get("/metrics", response_model=DiscoveryMetrics)
def discovery_metrics(
    db: Session = Depends(get_db),
    _: AdminUser = Depends(auth),
):
    return get_discovery_metrics(db)


@router.get("/candidates", response_model=list[DiscoveryCandidateRead])
def get_recent_candidate_exceptions(
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: AdminUser = Depends(auth),
):
    """Retrieves recent candidate exceptions from runs with validation failures."""
    runs = db.scalars(
        select(DiscoveryRun)
        .where(DiscoveryRun.validation_failures > 0)
        .order_by(desc(DiscoveryRun.started_at))
        .limit(10)
    ).all()

    candidates: list[DiscoveryCandidateRead] = []
    for r in runs:
        exceptions = (r.metrics or {}).get("validation_exceptions", [])
        for exc in exceptions:
            candidates.append(
                DiscoveryCandidateRead(
                    title=exc.get("title", "Unknown"),
                    source_url=exc.get("url", ""),
                    source_name=r.source.name if r.source else None,
                    validation_status="invalid",
                    rejection_reasons=exc.get("reasons", []),
                    confidence_score=0.0,
                )
            )
            if len(candidates) >= limit:
                break
        if len(candidates) >= limit:
            break
    return candidates


@router.get("/events/{event_id}/sources", response_model=list[EventSourceRead])
def get_event_sources(
    event_id: int,
    db: Session = Depends(get_db),
    _: AdminUser = Depends(auth),
):
    sources = db.scalars(
        select(EventSource)
        .where(EventSource.event_id == event_id)
        .order_by(EventSource.first_seen)
    ).all()

    return [
        EventSourceRead(
            id=s.id,
            event_id=s.event_id,
            source_id=s.source_id,
            source_name=s.source.name if s.source else None,
            external_event_id=s.external_event_id,
            source_event_url=s.source_event_url,
            canonical_url=s.canonical_url,
            content_hash=s.content_hash,
            first_seen=s.first_seen,
            last_seen=s.last_seen,
            last_checked=s.last_checked,
        )
        for s in sources
    ]


@router.get("/review-queue", response_model=list[EventRead])
def get_review_queue(
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: AdminUser = Depends(auth),
):
    """Retrieves discovered events awaiting manual review."""
    events = db.scalars(
        select(Event)
        .where(
            or_(
                Event.validation_outcome == "needs_review",
                Event.status == "pending",
            )
        )
        .order_by(desc(Event.created_at))
        .limit(limit)
    ).all()
    return events


@router.get("/published-events", response_model=list[EventRead])
def get_published_events(
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: AdminUser = Depends(auth),
):
    """Retrieves discovered events that have been auto-published or published."""
    events = db.scalars(
        select(Event)
        .where(
            or_(
                Event.validation_outcome == "auto_published",
                Event.is_published.is_(True),
                Event.status == "published",
            )
        )
        .order_by(desc(Event.created_at))
        .limit(limit)
    ).all()
    return events


# ==========================================
# Lifecycle Diagnostics & Reconciliation
# ==========================================

@router.get("/lifecycle/diagnostics")
def get_lifecycle_diagnostics(
    db: Session = Depends(get_db),
    _: AdminUser = Depends(auth),
) -> dict[str, Any]:
    """Calculates database-wide event lifecycle and temporal diagnostics."""
    return compute_database_diagnostics(db)


@router.post("/lifecycle/reconcile")
def run_lifecycle_reconciliation(
    dry_run: bool = Query(default=True, description="When true, performs simulation without persisting changes"),
    db: Session = Depends(get_db),
    _: AdminUser = Depends(auth),
) -> dict[str, Any]:
    """Generates a dry-run or applied reconciliation report for event lifecycles."""
    return reconcile_event_lifecycle(db, dry_run=dry_run, preserve_manual_cancellations=True)
