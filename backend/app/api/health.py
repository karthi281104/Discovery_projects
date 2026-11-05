from fastapi import APIRouter, HTTPException

from app.db.session import check_database_connection

router = APIRouter(tags=["health"])


@router.get("/health", summary="Service health check")
def health_check() -> dict[str, object]:
    """Report API and database health; return 503 if the database is unavailable."""
    try:
        check_database_connection()
    except Exception as exc:  # Keep infrastructure details out of the public response.
        raise HTTPException(
            status_code=503,
            detail={"status": "unhealthy", "database": "unavailable"},
        ) from exc

    return {"status": "ok", "service": "tamil-event-discovery-api", "database": "connected"}
