import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.orm import Session

from app.models import AdminUser, Category, Event, Location
from app.schemas import CategoryCreate, CategoryUpdate, EventCreate, EventUpdate, LocationCreate, LocationUpdate

KOLKATA_TZ = ZoneInfo("Asia/Kolkata")


def get_current_kolkata_time() -> datetime:
    return datetime.now(KOLKATA_TZ)


def _slugify(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return cleaned or "event"


def generate_unique_event_slug(db: Session, base_title: str, current_event_id: int | None = None) -> str:
    base_slug = _slugify(base_title)
    slug = base_slug
    counter = 1
    while True:
        existing = db.scalar(select(Event.id).where(Event.slug == slug))
        if existing is None or existing == current_event_id:
            return slug
        counter += 1
        slug = f"{base_slug}-{counter}"


def list_events(
    db: Session,
    *,
    category_id: int | None = None,
    city: str | None = None,
    search: str | None = None,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    event_type: str | None = None,
    mode: str | None = None,
    district: str | None = None,
    status_filter: str | None = None,
    time: str | None = None,
    limit: int = 50,
    offset: int = 0,
    published_only: bool = True,
    category_slug: str | None = None,
    featured: bool | None = None,
    sort: str = "start_date",
) -> tuple[list[Event], int]:
    query = select(Event)

    if published_only:
        query = query.where(Event.is_published.is_(True), Event.status == "published")
    elif status_filter:
        query = query.where(Event.status == status_filter)

    if category_id:
        query = query.where(Event.category_id == category_id)

    if category_slug:
        query = query.join(Event.category).where(Category.slug == category_slug)

    if city:
        query = query.where(Event.city.ilike(f"%{city}%"))

    if district:
        query = query.where(Event.district.ilike(f"%{district}%"))

    if search:
        search_pattern = f"%{search}%"
        query = query.where(
            or_(
                Event.title.ilike(search_pattern),
                Event.description.ilike(search_pattern),
                Event.short_description.ilike(search_pattern),
                Event.organizer_name.ilike(search_pattern),
            )
        )

    start_col = func.coalesce(Event.start_date, Event.starts_at)
    end_col = func.coalesce(Event.end_date, Event.ends_at)

    if from_date:
        query = query.where(start_col >= from_date)

    if to_date:
        query = query.where(start_col <= to_date)

    if event_type:
        query = query.where(Event.event_type == event_type)

    if mode:
        query = query.where(Event.mode == mode)

    # Lifecycle is evaluated in Python using the same policy as the worker.
    # This avoids SQL approximations that misclassify date-only and missing-end events.

    if featured is not None:
        query = query.where(Event.is_featured.is_(featured))

    # Sort
    if sort not in {"start_date", "-start_date", "created_at", "-created_at"}:
        sort = "start_date"

    order_target = start_col if "start_date" in sort else Event.created_at
    order_clause = desc(order_target) if sort.startswith("-") else order_target

    if time:
        from app.discovery.lifecycle import classify_event_lifecycle
        all_matching = list(db.scalars(query.order_by(order_clause)).all())
        if time == "active":
            allowed = {"upcoming", "ongoing"}
        elif time == "past":
            allowed = {"past", "expired"}
        else:
            allowed = {time}
        filtered = [
            event for event in all_matching
            if classify_event_lifecycle(event) in allowed
        ]
        total = len(filtered)
        items = filtered[offset:offset + limit]
        return items, total

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    items = list(db.scalars(query.order_by(order_clause).offset(offset).limit(limit)).all())
    return items, total


def create_event(db: Session, data: EventCreate) -> Event:
    values = data.model_dump()
    values.pop("category", None)
    values.pop("location", None)

    # Slug handling
    explicit_slug = values.get("slug")
    if explicit_slug:
        clean_slug = _slugify(explicit_slug)
        existing = db.scalar(select(Event).where(Event.slug == clean_slug))
        if existing:
            raise HTTPException(status.HTTP_409_CONFLICT, f"Event with slug '{clean_slug}' already exists")
        values["slug"] = clean_slug
    else:
        values["slug"] = generate_unique_event_slug(db, values["title"])

    # Legacy field synchronization
    values["starts_at"] = values.get("start_date")
    values["ends_at"] = values.get("end_date")
    values["organizer"] = values.get("organizer_name")
    values["ticket_url"] = values.get("registration_url")
    values["image_url"] = values.get("banner_url")

    # Status and publication consistency
    if values.get("status") == "published":
        values["is_published"] = True
    elif values.get("is_published"):
        values["status"] = "published"
    else:
        values["is_published"] = False

    event = Event(**values)
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def update_event(db: Session, event_id: int, data: EventUpdate | EventCreate) -> Event:
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Event not found")

    values = data.model_dump(exclude_unset=isinstance(data, EventUpdate))
    values.pop("category", None)
    values.pop("location", None)

    # Date range validation if both or one updated
    new_start = values.get("start_date", event.start_date)
    new_end = values.get("end_date", event.end_date)
    if new_start and new_end and new_end < new_start:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "end_date must not be earlier than start_date")

    new_deadline = values.get("registration_deadline", event.registration_deadline)
    if new_deadline and new_start and new_deadline > new_start:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "registration_deadline must not be after start_date")

    # Slug handling if changed
    if "slug" in values and values["slug"]:
        clean_slug = _slugify(values["slug"])
        existing = db.scalar(select(Event).where(Event.slug == clean_slug, Event.id != event_id))
        if existing:
            raise HTTPException(status.HTTP_409_CONFLICT, f"Event with slug '{clean_slug}' already exists")
        values["slug"] = clean_slug

    # Legacy synchronization
    if "start_date" in values:
        values["starts_at"] = values["start_date"]
    if "end_date" in values:
        values["ends_at"] = values["end_date"]
    if "organizer_name" in values:
        values["organizer"] = values["organizer_name"]
    if "registration_url" in values:
        values["ticket_url"] = values["registration_url"]
    if "banner_url" in values:
        values["image_url"] = values["banner_url"]

    # Status/publication synchronization
    if "status" in values:
        target_status = values["status"]
        if target_status != event.status:
            validate_event_status_transition(event.status, target_status)
        if target_status == "published":
            values["is_published"] = True
        else:
            values["is_published"] = False
    elif "is_published" in values:
        if values["is_published"]:
            if event.status != "published":
                validate_event_status_transition(event.status, "published")
            values["status"] = "published"
        elif event.status == "published":
            values["status"] = "draft"

    for key, value in values.items():
        setattr(event, key, value)

    if event.status == "published":
        validate_publish_requirements(event)

    db.commit()
    db.refresh(event)
    return event


VALID_TRANSITIONS: dict[str, set[str]] = {
    "draft": {"draft", "pending", "published", "rejected", "cancelled"},
    "pending": {"pending", "draft", "published", "rejected", "cancelled"},
    "published": {"published", "draft", "rejected", "cancelled", "expired"},
    "rejected": {"rejected", "draft", "pending", "published"},
    "cancelled": {"cancelled", "draft"},
    "expired": {"expired", "draft"},
}


def validate_event_status_transition(current_status: str, target_status: str) -> None:
    allowed = VALID_TRANSITIONS.get(current_status, {"draft"})
    if target_status not in allowed:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Invalid status transition from '{current_status}' to '{target_status}'. "
            f"Cancelled or expired events must be moved to 'draft' first.",
        )


def validate_publish_requirements(event: Event) -> None:
    missing = []
    if not event.title or not event.title.strip():
        missing.append("title")
    if not event.description or not event.description.strip():
        missing.append("description")
    if not event.organizer_name or not event.organizer_name.strip():
        missing.append("organizer_name")
    if not event.start_date:
        missing.append("start_date")
    if not event.registration_url or not event.registration_url.strip():
        missing.append("registration_url")

    if missing:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Cannot publish event missing required fields: {', '.join(missing)}",
        )


def delete_event(db: Session, event_id: int) -> None:
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Event not found")
    db.delete(event)
    db.commit()


def set_event_status(db: Session, event_id: int, status_name: str) -> Event:
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Event not found")

    validate_event_status_transition(event.status, status_name)
    if status_name == "published":
        validate_publish_requirements(event)

    event.status = status_name
    event.is_published = status_name == "published"
    db.commit()
    db.refresh(event)
    return event


def toggle_event_feature(db: Session, event_id: int, explicit_state: bool | None = None) -> Event:
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Event not found")

    if explicit_state is not None:
        event.is_featured = explicit_state
    else:
        event.is_featured = not event.is_featured

    db.commit()
    db.refresh(event)
    return event


def create_category(db: Session, data: CategoryCreate) -> Category:
    slug = _slugify(data.slug or data.name)
    existing = db.scalar(select(Category).where(or_(Category.name == data.name, Category.slug == slug)))
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Category with name or slug '{slug}' already exists")
    values = data.model_dump()
    values["slug"] = slug
    item = Category(**values)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def update_category(db: Session, category_id: int, data: CategoryUpdate) -> Category:
    item = db.get(Category, category_id)
    if not item:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Category not found")
    values = data.model_dump(exclude_unset=True)
    if "slug" in values and values["slug"]:
        slug = _slugify(values["slug"])
        existing = db.scalar(select(Category).where(Category.slug == slug, Category.id != category_id))
        if existing:
            raise HTTPException(status.HTTP_409_CONFLICT, f"Category with slug '{slug}' already exists")
        values["slug"] = slug
    for key, value in values.items():
        setattr(item, key, value)
    db.commit()
    db.refresh(item)
    return item


def delete_category(db: Session, category_id: int) -> None:
    item = db.get(Category, category_id)
    if not item:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Category not found")
    # Deactivate or delete
    db.delete(item)
    db.commit()


def create_location(db: Session, data: LocationCreate) -> Location:
    item = Location(**data.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def update_location(db: Session, location_id: int, data: LocationUpdate) -> Location:
    item = db.get(Location, location_id)
    if not item:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Location not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(item, key, value)
    db.commit()
    db.refresh(item)
    return item


def delete_location(db: Session, location_id: int) -> None:
    item = db.get(Location, location_id)
    if not item:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Location not found")
    db.delete(item)
    db.commit()


def get_admin_metrics(db: Session) -> dict[str, int]:
    total_events = db.scalar(select(func.count(Event.id))) or 0
    published_events = db.scalar(select(func.count(Event.id)).where(Event.status == "published")) or 0
    draft_events = db.scalar(select(func.count(Event.id)).where(Event.status == "draft")) or 0
    pending_events = db.scalar(select(func.count(Event.id)).where(Event.status == "pending")) or 0
    rejected_events = db.scalar(select(func.count(Event.id)).where(Event.status == "rejected")) or 0
    cancelled_events = db.scalar(select(func.count(Event.id)).where(Event.status == "cancelled")) or 0
    expired_events = db.scalar(select(func.count(Event.id)).where(Event.status == "expired")) or 0
    featured_events = db.scalar(select(func.count(Event.id)).where(Event.is_featured.is_(True))) or 0
    total_categories = db.scalar(select(func.count(Category.id))) or 0
    total_locations = db.scalar(select(func.count(Location.id))) or 0

    return {
        "total_events": total_events,
        "published_events": published_events,
        "draft_events": draft_events,
        "pending_events": pending_events,
        "rejected_events": rejected_events,
        "cancelled_events": cancelled_events,
        "expired_events": expired_events,
        "featured_events": featured_events,
        "total_categories": total_categories,
        "total_locations": total_locations,
    }
