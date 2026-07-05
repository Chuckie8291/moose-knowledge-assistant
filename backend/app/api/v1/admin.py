"""
Admin API — System administration endpoints.

GET  /api/v1/admin/health     — System health check
GET  /api/v1/admin/stats      — System statistics (stub)
POST /api/v1/admin/reindex    — Trigger re-indexing (stub)
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.config import settings
from app.utils.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()


class HealthResponse(BaseModel):
    status: str
    version: str
    services: dict


class StatsResponse(BaseModel):
    total_documents: int = 0
    total_chunks: int = 0
    total_queries: int = 0
    active_users: int = 0


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Check system health and service connectivity."""
    services = {
        "api": "online",
        "database": "not_connected",    # Stub — requires actual PG connection
        "elasticsearch": "not_connected",  # Stub
        "redis": "not_connected",       # Stub
        "llm_provider": settings.llm_provider,
    }
    return HealthResponse(
        status="ok" if all(v == "online" or v == "not_connected" for v in services.values()) else "degraded",
        version=settings.app_version,
        services=services,
    )


@router.get("/stats", response_model=StatsResponse)
async def get_stats():
    """Get system statistics. Stub — requires database."""
    return StatsResponse()
