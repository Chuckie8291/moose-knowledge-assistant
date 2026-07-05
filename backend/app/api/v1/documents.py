"""
Documents API — Upload, list, and manage documents.

POST   /api/v1/documents/upload    — Upload a new document for ingestion
GET    /api/v1/documents           — List documents
GET    /api/v1/documents/{id}      — Get document details
GET    /api/v1/documents/{id}/sections — Get section tree
"""

from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from pydantic import BaseModel, Field

from app.core.ingestion.pipeline import IngestionPipeline
from app.utils.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()


# ── Schemas ──────────────────────────────────────────────────

class DocumentUploadRequest(BaseModel):
    title: str = Field(..., description="Document title")
    doc_type: str | None = Field(default=None, description="Override auto-detected type")
    effective_date: str | None = Field(default=None, description="Effective date (YYYY-MM-DD)")
    access_level: str = Field(default="public")
    is_new_version_of: str | None = Field(default=None, description="Parent document ID")


class DocumentResponse(BaseModel):
    id: str
    title: str
    doc_type: str
    tier: int
    status: str
    total_pages: int
    total_chunks: int
    created_at: str | None = None


class IngestionStatusResponse(BaseModel):
    document_id: str
    version_id: str
    status: str  # received, processing, active, error
    total_pages: int
    total_chunks: int
    errors: list[str] = []
    warnings: list[str] = []


# ── Endpoints ────────────────────────────────────────────────

@router.post("/upload", response_model=IngestionStatusResponse)
async def upload_document(
    file: UploadFile = File(...),
    title: str = Form(...),
    doc_type: str | None = Form(default=None),
    effective_date: str | None = Form(default=None),
    access_level: str = Form(default="public"),
):
    """
    Upload a document for ingestion into the knowledge base.

    Accepts PDF, DOCX, TXT, and image files.
    Runs the full ingestion pipeline asynchronously.
    """
    # Validate file type
    allowed_extensions = {'.pdf', '.docx', '.doc', '.txt', '.png', '.jpg', '.jpeg', '.tiff', '.tif'}
    ext = Path(file.filename or "unknown").suffix.lower()
    if ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {ext}. Allowed: {allowed_extensions}"
        )

    # Save file temporarily
    temp_dir = Path("tmp/uploads")
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp_path = temp_dir / f"{uuid.uuid4()}{ext}"

    try:
        content = await file.read()
        temp_path.write_bytes(content)

        # Run ingestion pipeline
        doc_id = str(uuid.uuid4())
        version_id = str(uuid.uuid4())

        pipeline = IngestionPipeline()
        result = pipeline.ingest(
            file_path=str(temp_path),
            document_id=doc_id,
            version_id=version_id,
            metadata={
                "title": title,
                "doc_type": doc_type,
                "effective_date": effective_date,
                "access_level": access_level,
            },
        )

        return IngestionStatusResponse(
            document_id=result.document_id,
            version_id=result.version_id,
            status=result.status,
            total_pages=result.total_pages,
            total_chunks=result.total_chunks,
            errors=result.errors,
            warnings=result.warnings,
        )

    except Exception as e:
        logger.exception("Upload failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {e}")

    finally:
        # Clean up temp file
        if temp_path.exists():
            temp_path.unlink()


@router.get("", response_model=list[DocumentResponse])
async def list_documents(
    doc_type: str | None = None,
    tier: int | None = None,
    status: str | None = None,
):
    """
    List documents in the knowledge base.

    NOTE: Stub — full implementation requires database connection.
    """
    logger.info("Document list requested (stub)")
    return []


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(document_id: str):
    """
    Get details for a specific document.

    NOTE: Stub — full implementation requires database connection.
    """
    logger.info("Document detail requested: %s (stub)", document_id)
    raise HTTPException(status_code=404, detail="Document not found (database not connected)")
