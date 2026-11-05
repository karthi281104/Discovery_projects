from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.dependencies import get_db
from app.models import Category, Event, Location
from app.schemas import CategoryRead, EventList, EventRead, LocationRead
from app.services import list_events

router = APIRouter(tags=["public"])


@router.get("/categories", response_model=list[CategoryRead])
def categories(db: Session = Depends(get_db)):
    return db.scalars(
        select(Category).where(Category.is_active.is_(True)).order_by(Category.name)
    ).all()


@router.get("/locations", response_model=list[LocationRead])
def locations(db: Session = Depends(get_db)):
    return db.scalars(
        select(Location).where(Location.is_active.is_(True)).order_by(Location.city, Location.name)
    ).all()


@router.get("/events", response_model=EventList)
def events(
    category_id: int | None = None,
    category: str | None = None,
    city: str | None = None,
    district: str | None = None,
    search: str | None = None,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    event_type: str | None = None,
    mode: str | None = None,
    time: Literal["upcoming", "ongoing", "past"] | None = None,
    featured: bool | None = None,
    sort: str = Query("start_date", pattern="^-?(start_date|created_at)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    items, total = list_events(
        db,
        category_id=category_id,
        category_slug=category,
        city=city,
        district=district,
        search=search,
        from_date=from_date,
        to_date=to_date,
        event_type=event_type,
        mode=mode,
        status_filter="published",
        time=time,
        featured=featured,
        sort=sort,
        limit=page_size,
        offset=(page - 1) * page_size,
        published_only=True,
    )
    pages = (total + page_size - 1) // page_size if total > 0 else 1
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": pages,
    }


@router.get("/events/featured", response_model=list[EventRead])
def featured_events(db: Session = Depends(get_db)):
    items, _ = list_events(db, featured=True, published_only=True, limit=20)
    return items


@router.get("/events/upcoming", response_model=list[EventRead])
def upcoming_events(db: Session = Depends(get_db)):
    items, _ = list_events(db, time="upcoming", published_only=True, limit=20)
    return items


@router.get("/events/{slug}", response_model=EventRead)
def event_detail(slug: str, db: Session = Depends(get_db)):
    item = db.scalar(
        select(Event).where(
            Event.slug == slug,
            Event.is_published.is_(True),
            Event.status == "published",
        )
    )
    if not item:
        raise HTTPException(404, "Event not found")
    return item
