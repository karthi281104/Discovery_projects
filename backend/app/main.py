import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.admin import router as admin_router
from app.api.health import router as health_router
from app.api.public import router as public_router
from app.core.config import settings
from app.core.security import hash_password
from app.db.session import engine
from app.models import AdminUser

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # In local development mode, automatically ensure Alembic migrations are up to date
    if settings.app_env.lower() == "development":
        try:
            from alembic import command
            from alembic.config import Config
            backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            alembic_ini = os.path.join(backend_dir, "alembic.ini")
            if os.path.exists(alembic_ini):
                config = Config(alembic_ini)
                config.set_main_option("script_location", os.path.join(backend_dir, "migrations"))
                command.upgrade(config, "head")
                logger.info("Alembic migrations verified up-to-date (head).")
        except Exception as exc:
            logger.warning("Auto-migration during development startup encountered: %s", exc)

    try:
        from sqlalchemy.orm import Session
        with Session(engine) as db:
            if not db.query(AdminUser).filter(AdminUser.email == settings.admin_email).first():
                if settings.app_env.lower() != "production" or settings.admin_password not in {"change-me", "admin"}:
                    db.add(AdminUser(email=settings.admin_email, password_hash=hash_password(settings.admin_password)))
                    db.commit()
                    logger.info("Initialized default admin user: %s", settings.admin_email)
    except Exception as exc:
        logger.error("Failed to initialize admin account during application startup: %s", exc)
        if settings.app_env.lower() == "production":
            raise RuntimeError(f"Startup initialization failed in production: {exc}") from exc
    yield


app = FastAPI(
    title=settings.app_name,
    description="Public event discovery API, initially focused on Tamil Nadu, India.",
    version="0.1.0",
    lifespan=lifespan,
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


@app.get("/", tags=["root"])
def root() -> dict[str, str]:
    return {"message": "Tamil Event Discovery API", "docs": "/docs", "health": "/api/v1/health"}
