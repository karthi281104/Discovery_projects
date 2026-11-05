from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.health import router as health_router
from app.api.public import router as public_router
from app.api.admin import router as admin_router
from app.db.base import Base
from app.db.session import engine
from app.models import AdminUser
from app.core.security import hash_password
from sqlalchemy import inspect, text
from app.core.config import settings

app = FastAPI(
    title=settings.app_name,
    description="Public event discovery API, initially focused on Tamil Nadu, India.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(health_router, prefix=settings.api_v1_prefix)
app.include_router(public_router, prefix=settings.api_v1_prefix)
app.include_router(admin_router, prefix=settings.api_v1_prefix)


@app.on_event("startup")
def initialize_database() -> None:
    Base.metadata.create_all(bind=engine)
    from sqlalchemy.orm import Session
    with Session(engine) as db:
        columns = {column["name"] for column in inspect(engine).get_columns("events")}
        if "slug" not in columns:
            db.execute(text("ALTER TABLE events ADD COLUMN slug VARCHAR(280)"))
            db.flush()
            for event in db.execute(text("SELECT id, title FROM events WHERE slug IS NULL")).mappings():
                import re
                slug = re.sub(r"[^a-z0-9]+", "-", event["title"].lower()).strip("-") or f"event-{event['id']}"
                db.execute(text("UPDATE events SET slug = :slug WHERE id = :id"), {"slug": f"{slug}-{event['id']}", "id": event["id"]})
        if "is_featured" not in columns:
            db.execute(text("ALTER TABLE events ADD COLUMN is_featured BOOLEAN DEFAULT 0"))
        additions = {
            "short_description": "TEXT", "start_date": "DATETIME", "end_date": "DATETIME",
            "organizer_name": "VARCHAR(180)", "registration_url": "VARCHAR(500)",
            "banner_url": "VARCHAR(500)", "event_type": "VARCHAR(40)",
            "mode": "VARCHAR(20)", "status": "VARCHAR(20)", "city": "VARCHAR(120)",
            "district": "VARCHAR(120)", "venue": "VARCHAR(240)", "state": "VARCHAR(120)",
        }
        for name, sql_type in additions.items():
            if name not in columns:
                db.execute(text(f"ALTER TABLE events ADD COLUMN {name} {sql_type}"))
        db.execute(text("UPDATE events SET start_date = starts_at WHERE start_date IS NULL"))
        db.execute(text("UPDATE events SET end_date = ends_at WHERE end_date IS NULL"))
        db.execute(text("UPDATE events SET organizer_name = organizer WHERE organizer_name IS NULL"))
        db.execute(text("UPDATE events SET registration_url = ticket_url WHERE registration_url IS NULL"))
        db.execute(text("UPDATE events SET status = CASE WHEN is_published = 1 THEN 'published' ELSE 'draft' END WHERE status IS NULL"))
        db.execute(text("UPDATE events SET event_type = 'other' WHERE event_type IS NULL"))
        db.execute(text("UPDATE events SET mode = 'offline' WHERE mode IS NULL"))
        db.execute(text("UPDATE events SET state = 'Tamil Nadu' WHERE state IS NULL"))
        db.commit()
        if not db.query(AdminUser).filter(AdminUser.email == settings.admin_email).first():
            db.add(AdminUser(email=settings.admin_email, password_hash=hash_password(settings.admin_password)))
            db.commit()


@app.get("/", tags=["root"])
def root() -> dict[str, str]:
    return {"message": "Tamil Event Discovery API", "docs": "/docs", "health": "/api/v1/health"}
