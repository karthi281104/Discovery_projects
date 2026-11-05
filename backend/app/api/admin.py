from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import get_current_admin, verify_password, create_access_token
from app.db.dependencies import get_db
from app.models import AdminUser, Category, Event, Location
from app.schemas import CategoryCreate, CategoryRead, EventCreate, EventList, EventRead, LocationCreate, LocationRead, LoginRequest, TokenResponse
from app.services import create_category, create_event, create_location

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/login", response_model=TokenResponse)
def login(data: LoginRequest, db: Session = Depends(get_db)):
    admin = db.scalar(select(AdminUser).where(AdminUser.email == data.email, AdminUser.is_active.is_(True)))
    if not admin or not verify_password(data.password, admin.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    return TokenResponse(access_token=create_access_token(admin.email))


def auth(admin: AdminUser = Depends(get_current_admin)) -> AdminUser:
    return admin


@router.post("/categories", response_model=CategoryRead, status_code=201)
def add_category(data: CategoryCreate, db: Session = Depends(get_db), _: AdminUser = Depends(auth)):
    return create_category(db, data)


@router.get("/categories", response_model=list[CategoryRead])
def list_categories(db: Session = Depends(get_db), _: AdminUser = Depends(auth)):
    return db.scalars(select(Category).order_by(Category.name)).all()


@router.put("/categories/{category_id}", response_model=CategoryRead)
def edit_category(category_id: int, data: CategoryCreate, db: Session = Depends(get_db), _: AdminUser = Depends(auth)):
    item = db.get(Category, category_id)
    if not item:
        raise HTTPException(404, "Category not found")
    for key, value in data.model_dump().items():
        setattr(item, key, value)
    db.commit(); db.refresh(item)
    return item


@router.delete("/categories/{category_id}", status_code=204)
def remove_category(category_id: int, db: Session = Depends(get_db), _: AdminUser = Depends(auth)):
    item = db.get(Category, category_id)
    if not item:
        raise HTTPException(404, "Category not found")
    db.delete(item); db.commit()


@router.post("/locations", response_model=LocationRead, status_code=201)
def add_location(data: LocationCreate, db: Session = Depends(get_db), _: AdminUser = Depends(auth)):
    return create_location(db, data)


@router.post("/events", response_model=EventRead, status_code=201)
def add_event(data: EventCreate, db: Session = Depends(get_db), _: AdminUser = Depends(auth)):
    return create_event(db, data)


@router.get("/events", response_model=EventList)
def all_events(page: int = 1, page_size: int = 20, db: Session = Depends(get_db), _: AdminUser = Depends(auth)):
    items = list(db.scalars(select(Event).order_by(Event.starts_at).offset((page - 1) * page_size).limit(page_size)).all())
    total = db.query(Event).count()
    return {"items": items, "total": total, "page": page, "page_size": page_size, "pages": (total + page_size - 1) // page_size}


@router.put("/events/{event_id}", response_model=EventRead)
def edit_event(event_id: int, data: EventCreate, db: Session = Depends(get_db), _: AdminUser = Depends(auth)):
    item = db.get(Event, event_id)
    if not item:
        raise HTTPException(404, "Event not found")
    for key, value in data.model_dump().items():
        setattr(item, key, value)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/events/{event_id}", status_code=204)
def remove_event(event_id: int, db: Session = Depends(get_db), _: AdminUser = Depends(auth)):
    item = db.get(Event, event_id)
    if not item:
        raise HTTPException(404, "Event not found")
    db.delete(item)
    db.commit()


def _event_action(event_id: int, action: str, db: Session) -> Event:
    item = db.get(Event, event_id)
    if not item:
        raise HTTPException(404, "Event not found")
    if action == "publish":
        item.is_published = True
        item.status = "published"
    elif action == "reject":
        item.is_published = False
        item.status = "rejected"
    else:
        item.is_featured = True
    db.commit(); db.refresh(item)
    return item


@router.patch("/events/{event_id}/publish", response_model=EventRead)
def publish_event(event_id: int, db: Session = Depends(get_db), _: AdminUser = Depends(auth)):
    return _event_action(event_id, "publish", db)


@router.patch("/events/{event_id}/reject", response_model=EventRead)
def reject_event(event_id: int, db: Session = Depends(get_db), _: AdminUser = Depends(auth)):
    return _event_action(event_id, "reject", db)


@router.patch("/events/{event_id}/feature", response_model=EventRead)
def feature_event(event_id: int, db: Session = Depends(get_db), _: AdminUser = Depends(auth)):
    return _event_action(event_id, "feature", db)
