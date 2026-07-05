"""
API v1 Router — Aggregates all v1 endpoint routers.
"""

from fastapi import APIRouter

from app.api.v1 import query, documents, admin

api_router = APIRouter()

api_router.include_router(query.router, prefix="/query", tags=["query"])
api_router.include_router(documents.router, prefix="/documents", tags=["documents"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
