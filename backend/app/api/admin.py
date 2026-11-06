from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import create_access_token, get_current_admin, verify_password
from app.db.dependencies import get_db
from app.models import AdminUser, Category, Event, Location
from app.schemas import (
    AdminMetrics,
    CategoryCreate,
    CategoryRead,
    CategoryUpdate,
    EventCreate,
    EventList,
    EventRead,
    EventUpdate,
    LocationCreate,
    LocationRead,
    LocationUpdate,
    LoginRequest,
    TokenResponse,
)
from app.services import (
    create_category,
    create_event,
    create_location,
    delete_category,
    delete_event,
    delete_location,
    get_admin_metrics,
    list_events,
    set_event_status,
    toggle_event_feature,
    update_category,
    update_event,
    update_location,
)

from app.api.discovery import router as discovery_router

router = APIRouter(prefix="/admin", tags=["admin"])
router.include_router(discovery_router)


def auth(admin: AdminUser = Depends(get_current_admin)) -> AdminUser:
    return admin


# ==========================================
# Authentication & Metrics
# ==========================================

@router.post("/login", response_model=TokenResponse)
def login(data: LoginRequest, db: Session = Depends(get_db)):
    admin = db.scalar(select(AdminUser).where(AdminUser.email == data.email, AdminUser.is_active.is_(True)))
    if not admin or not verify_password(data.password, admin.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    return TokenResponse(access_token=create_access_token(admin.email))


@router.get("/metrics", response_model=AdminMetrics)
def metrics(db: Session = Depends(get_db), _: AdminUser = Depends(auth)):
    return get_admin_metrics(db)


# ==========================================
# Event Administration
# ==========================================

@router.get("/events", response_model=EventList)
def all_events(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: str | None = Query(None, alias="status"),
    category_id: int | None = None,
    city: str | None = None,
    district: str | None = None,
    search: str | None = None,
    featured: bool | None = None,
    mode: str | None = None,
    sort: str = Query("-created_at"),
    db: Session = Depends(get_db),
    _: AdminUser = Depends(auth),
):
    items, total = list_events(
        db,
        category_id=category_id,
        city=city,
        district=district,
        search=search,
        status_filter=status_filter,
        featured=featured,
        mode=mode,
        sort=sort,
        limit=page_size,
        offset=(page - 1) * page_size,
        published_only=False,
    )
    pages = (total + page_size - 1) // page_size if total > 0 else 1
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": pages,
    }


@router.post("/events", response_model=EventRead, status_code=201)
def add_event(data: EventCreate, db: Session = Depends(get_db), _: AdminUser = Depends(auth)):
    return create_event(db, data)


@router.get("/events/{event_id}", response_model=EventRead)
def get_event_detail(event_id: int, db: Session = Depends(get_db), _: AdminUser = Depends(auth)):
    item = db.get(Event, event_id)
    if not item:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Event not found")
    return item


@router.put("/events/{event_id}", response_model=EventRead)
def edit_event(event_id: int, data: EventUpdate, db: Session = Depends(get_db), _: AdminUser = Depends(auth)):
    return update_event(db, event_id, data)


@router.delete("/events/{event_id}", status_code=204)
def remove_event(event_id: int, db: Session = Depends(get_db), _: AdminUser = Depends(auth)):
    delete_event(db, event_id)


@router.patch("/events/{event_id}/publish", response_model=EventRead)
def publish_event(event_id: int, db: Session = Depends(get_db), _: AdminUser = Depends(auth)):
    return set_event_status(db, event_id, "published")


@router.patch("/events/{event_id}/reject", response_model=EventRead)
def reject_event(event_id: int, db: Session = Depends(get_db), _: AdminUser = Depends(auth)):
    return set_event_status(db, event_id, "rejected")


@router.patch("/events/{event_id}/feature", response_model=EventRead)
def feature_event(
    event_id: int,
    state: bool | None = Query(None, description="Explicit featured state; if omitted, toggles"),
    db: Session = Depends(get_db),
    _: AdminUser = Depends(auth),
):
    return toggle_event_feature(db, event_id, explicit_state=state)


@router.patch("/events/{event_id}/unfeature", response_model=EventRead)
def unfeature_event(event_id: int, db: Session = Depends(get_db), _: AdminUser = Depends(auth)):
    return toggle_event_feature(db, event_id, explicit_state=False)


# ==========================================
# Category Administration
# ==========================================

@router.get("/categories", response_model=list[CategoryRead])
def list_admin_categories(db: Session = Depends(get_db), _: AdminUser = Depends(auth)):
    return db.scalars(select(Category).order_by(Category.name)).all()


@router.post("/categories", response_model=CategoryRead, status_code=201)
def add_category(data: CategoryCreate, db: Session = Depends(get_db), _: AdminUser = Depends(auth)):
    return create_category(db, data)


@router.get("/categories/{category_id}", response_model=CategoryRead)
def get_category_detail(category_id: int, db: Session = Depends(get_db), _: AdminUser = Depends(auth)):
    item = db.get(Category, category_id)
    if not item:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Category not found")
    return item


@router.put("/categories/{category_id}", response_model=CategoryRead)
def edit_category(category_id: int, data: CategoryUpdate, db: Session = Depends(get_db), _: AdminUser = Depends(auth)):
    return update_category(db, category_id, data)


@router.patch("/categories/{category_id}/deactivate", response_model=CategoryRead)
def deactivate_category(category_id: int, db: Session = Depends(get_db), _: AdminUser = Depends(auth)):
    item = db.get(Category, category_id)
    if not item:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Category not found")
    item.is_active = not item.is_active
    db.commit()
    db.refresh(item)
    return item


@router.delete("/categories/{category_id}", status_code=204)
def remove_category(category_id: int, db: Session = Depends(get_db), _: AdminUser = Depends(auth)):
    delete_category(db, category_id)


# ==========================================
# Location Administration
# ==========================================

@router.get("/locations", response_model=list[LocationRead])
def list_admin_locations(db: Session = Depends(get_db), _: AdminUser = Depends(auth)):
    return db.scalars(select(Location).order_by(Location.city, Location.name)).all()


@router.post("/locations", response_model=LocationRead, status_code=201)
def add_location(data: LocationCreate, db: Session = Depends(get_db), _: AdminUser = Depends(auth)):
    return create_location(db, data)


@router.get("/locations/{location_id}", response_model=LocationRead)
def get_location_detail(location_id: int, db: Session = Depends(get_db), _: AdminUser = Depends(auth)):
    item = db.get(Location, location_id)
    if not item:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Location not found")
    return item


@router.put("/locations/{location_id}", response_model=LocationRead)
def edit_location(location_id: int, data: LocationUpdate, db: Session = Depends(get_db), _: AdminUser = Depends(auth)):
    return update_location(db, location_id, data)


@router.delete("/locations/{location_id}", status_code=204)
def remove_location(location_id: int, db: Session = Depends(get_db), _: AdminUser = Depends(auth)):
    delete_location(db, location_id)
