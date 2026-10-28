# This project was developed with assistance from AI tools.
"""Health check endpoints."""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends

from .. import __version__
from ..agents.mcp_integration import get_mcp_tools
from ..schemas.health import HealthResponse
from ..services.storage import is_storage_initialized

try:
    from db import DatabaseService, get_db_service  # type: ignore[import-untyped]
except Exception:
    # DB package not available or untyped
    DatabaseService = None  # type: ignore[assignment]
    get_db_service = None  # type: ignore[assignment]

# Capture API service startup time
API_START_TIME = datetime.now(UTC)

router = APIRouter()


@router.get("/dependencies")
async def dependency_initialization_status() -> dict[str, bool | str]:
    """Read process-local state only; this does not probe upstream health."""
    return {
        "scope": "process_memory_only",
        "storage_initialized": is_storage_initialized(),
        "mcp_tools_loaded": bool(get_mcp_tools()),
    }


@router.get("/", response_model=list[HealthResponse])
async def health_check(
    db_service: DatabaseService | None = Depends(get_db_service) if get_db_service else None,
) -> list[HealthResponse]:
    """Health check endpoint with dependency injection"""
    api_response = HealthResponse(
        name="API",
        status="healthy",
        message="API is running",
        version=__version__,
        start_time=API_START_TIME.isoformat(),
    )

    # Get database health using dependency injection
    responses = [api_response]
    if db_service:
        db_health = await db_service.health_check()
        db_response = HealthResponse(**db_health)
        responses.append(db_response)

    return responses
