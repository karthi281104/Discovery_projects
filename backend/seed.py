from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from app.db.session import engine
from app.models import Category, Location, Event
from sqlalchemy.orm import Session

with Session(engine) as db:
    category = db.scalar(select(Category).where(Category.slug == "cultural"))
    if not category:
        category = Category(name="Cultural", slug="cultural", description="Tamil cultural events")
        db.add(category)
    location = db.scalar(select(Location).where(Location.name == "Chennai Trade Centre"))
    if not location:
        location = Location(name="Chennai Trade Centre", city="Chennai", state="Tamil Nadu")
        db.add(location)
    db.flush()
    if not db.scalar(select(Event).where(Event.title == "Tamil Cultural Festival")):
        db.add(Event(title="Tamil Cultural Festival", description="A celebration of Tamil arts.",
                     starts_at=datetime.now(timezone.utc) + timedelta(days=14),
                     category_id=category.id, location_id=location.id, is_published=True))
    db.commit()
