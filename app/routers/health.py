"""
Health Check Router

Provides endpoints for system health monitoring, database status,
and dependency checks.
"""

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Dict, Any
from datetime import datetime,timezone
import logging

from app.config import settings
from app.database import check_db_connection

logger = logging.getLogger(__name__)

# Create router
router = APIRouter()


# ============================================================================
# RESPONSE MODELS
# ============================================================================

class HealthResponse(BaseModel):
    """Health check response model."""

    status: str
    timestamp: str
    version: str
    environment: str
    checks: Dict[str, Any]


class PingResponse(BaseModel):
    """Simple ping response model."""

    status: str
    timestamp: str


# ============================================================================
# ENDPOINTS
# ============================================================================

@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Comprehensive health check",
    description="Check overall system health including database and dependencies",
    tags=["Health"],
)
async def health_check() -> HealthResponse:
    """
    Comprehensive health check endpoint.

    Checks:
    - Database connectivity
    - System configuration
    - Application status

    Returns:
        HealthResponse: Detailed health status
    """
    # Check database
    db_healthy = await check_db_connection()

    # Overall status
    overall_status = "healthy" if db_healthy else "unhealthy"

    # Build response
    health_data = HealthResponse(
        status=overall_status,
        timestamp=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        version=settings.app_version,
        environment=settings.environment,
        checks={
            "database": {
                "status": "healthy" if db_healthy else "unhealthy",
                "type": "postgresql",
                "pool_size": settings.database_pool_size,
            },
            "redis": {
                "status": "healthy" if settings.redis_enabled else "disabled",
                "enabled": settings.redis_enabled,
            },
            "groq_ai": {
                "status": "configured" if settings.groq_api_key else "not_configured",
                "model": settings.groq_model,
            },
        },
    )

    # Log health check
    logger.info(
        f"Health check: {overall_status}",
        extra={
            "status": overall_status,
            "db_healthy": db_healthy,
        },
    )

    # Return appropriate status code
    if overall_status == "healthy":
        return health_data
    else:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=health_data.model_dump(),
        )


@router.get(
    "/ping",
    response_model=PingResponse,
    status_code=status.HTTP_200_OK,
    summary="Simple ping check",
    description="Quick response check without dependency verification",
    tags=["Health"],
)
async def ping() -> PingResponse:
    """
    Simple ping endpoint.

    Returns immediate response without checking dependencies.
    Useful for basic liveness checks.

    Returns:
        PingResponse: Simple status
    """
    return PingResponse(
        status="ok",
        timestamp=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    )


@router.get(
    "/ready",
    status_code=status.HTTP_200_OK,
    summary="Readiness check",
    description="Check if application is ready to accept requests",
    tags=["Health"],
)
async def readiness() -> Dict[str, Any]:
    """
    Readiness check endpoint.

    Used by Kubernetes to determine if pod is ready to receive traffic.
    Checks all critical dependencies.

    Returns:
        dict: Readiness status
    """
    # Check database
    db_healthy = await check_db_connection()

    # Application is ready if database is healthy
    is_ready = db_healthy

    if is_ready:
        return {
            "status": "ready",
            "timestamp":datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }
    else:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "not_ready",
                "reason": "database_unhealthy",
                "timestamp":datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            },
        )


@router.get(
    "/live",
    status_code=status.HTTP_200_OK,
    summary="Liveness check",
    description="Check if application is alive (no dependency checks)",
    tags=["Health"],
)
async def liveness() -> Dict[str, str]:
    """
    Liveness check endpoint.

    Used by Kubernetes to determine if pod is alive and shouldn't be restarted.
    Returns 200 OK if application is running, regardless of dependencies.

    Returns:
        dict: Liveness status
    """
    return {
        "status": "alive",
        "timestamp":datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
