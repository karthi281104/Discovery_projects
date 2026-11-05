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
def ensure_default_admin() -> None:
    try:
        from sqlalchemy.orm import Session
        with Session(engine) as db:
            if not db.query(AdminUser).filter(AdminUser.email == settings.admin_email).first():
                db.add(AdminUser(email=settings.admin_email, password_hash=hash_password(settings.admin_password)))
                db.commit()
    except Exception:
        pass


@app.get("/", tags=["root"])
def root() -> dict[str, str]:
    return {"message": "Tamil Event Discovery API", "docs": "/docs", "health": "/api/v1/health"}
