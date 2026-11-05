from datetime import datetime

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.models import Category, Event, Location
from app.schemas import CategoryCreate, EventCreate, LocationCreate


def list_events(db: Session, *, category_id: int | None = None, city: str | None = None,
                search: str | None = None, from_date: datetime | None = None,
                to_date: datetime | None = None, event_type: str | None = None,
                mode: str | None = None, district: str | None = None,
                status: str | None = None, time: str | None = None,
                limit: int = 50, offset: int = 0, published_only: bool = True,
                category_slug: str | None = None, featured: bool | None = None,
                sort: str = "start_date") -> tuple[list[Event], int]:
    query = select(Event).where(Event.is_published.is_(True) if published_only else True)
    start = func.coalesce(Event.start_date, Event.starts_at)
    end = func.coalesce(Event.end_date, Event.ends_at)
    if category_id:
        query = query.where(Event.category_id == category_id)
    if category_slug:
        query = query.join(Event.category).where(Category.slug == category_slug)
    if city:
        query = query.where(Event.city.ilike(f"%{city}%"))
    if search:
        query = query.where(Event.title.ilike(f"%{search}%"))
    if from_date:
        query = query.where(start >= from_date)
    if to_date:
        query = query.where(start <= to_date)
    if event_type:
        query = query.where(Event.event_type == event_type)
    if mode:
        query = query.where(Event.mode == mode)
    if district:
        query = query.where(Event.district.ilike(f"%{district}%"))
    if status:
        query = query.where(Event.status == status)
    if time:
        now = datetime.now()
        if time == "upcoming":
            query = query.where(start >= now)
        elif time == "ongoing":
            query = query.where(start <= now, end >= now)
        elif time == "past":
            query = query.where(end < now)
    if sort not in {"start_date", "-start_date", "created_at", "-created_at"}:
        sort = "start_date"
    if featured is not None:
        query = query.where(Event.is_featured.is_(featured))
    order_column = start if "start_date" in sort else Event.created_at
    ordering = desc(order_column) if sort.startswith("-") else order_column
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    return list(db.scalars(query.order_by(ordering).offset(offset).limit(limit)).all()), total


def create_event(db: Session, data: EventCreate) -> Event:
    values = data.model_dump()
    values["slug"] = values["slug"] or _slugify(values["title"])
    values["starts_at"] = values["starts_at"] or values["start_date"]
    values["ends_at"] = values["ends_at"] or values["end_date"]
    values["organizer"] = values["organizer"] or values["organizer_name"]
    values["ticket_url"] = values["ticket_url"] or values["registration_url"]
    values.pop("category", None)
    values.pop("location", None)
    event = Event(**values)
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def _slugify(value: str) -> str:
    import re
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def create_category(db: Session, data: CategoryCreate) -> Category:
    item = Category(**data.model_dump())
    db.add(item); db.commit(); db.refresh(item)
    return item


def create_location(db: Session, data: LocationCreate) -> Location:
    item = Location(**data.model_dump())
    db.add(item); db.commit(); db.refresh(item)
    return item
