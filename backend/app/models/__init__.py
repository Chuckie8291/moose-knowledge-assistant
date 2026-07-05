"""
SQLAlchemy ORM models for the Moose Knowledge Assistant.

Tables:
  - users, roles, user_roles      (authentication & authorization)
  - documents, document_versions  (document management)
  - sections, chunks              (content & embeddings)
  - chunk_embeddings              (multi-variant embeddings)
  - query_logs, feedback          (analytics & improvement)
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any, Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.dependencies import Base


# ── Authentication ───────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    external_id: Mapped[Optional[str]] = mapped_column(
        String(255), unique=True, nullable=True, index=True
    )  # Auth0 subject
    lodge_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), onupdate=func.now()
    )

    # Relationships
    roles: Mapped[list["Role"]] = relationship(
        secondary="user_roles", back_populates="users", lazy="selectin"
    )
    query_logs: Mapped[list["QueryLog"]] = relationship(back_populates="user")
    uploaded_documents: Mapped[list["Document"]] = relationship(
        back_populates="created_by_user", foreign_keys="Document.created_by"
    )

    def __repr__(self) -> str:
        return f"<User {self.email}>"


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False
    )  # member, officer, administrator, super_admin
    permissions: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    users: Mapped[list["User"]] = relationship(
        secondary="user_roles", back_populates="roles"
    )

    def __repr__(self) -> str:
        return f"<Role {self.name}>"


class UserRole(Base):
    __tablename__ = "user_roles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    role_id: Mapped[int] = mapped_column(
        ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True
    )
    lodge_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


# ── Documents ────────────────────────────────────────────────

class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    short_title: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    doc_type: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )  # general_laws, officer_handbook, etc.
    tier: Mapped[int] = mapped_column(Integer, nullable=False, index=True)  # 1-13
    category: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # governing, ritual, operational, etc.
    access_level: Mapped[str] = mapped_column(
        String(20), default="public"
    )  # public, member, officer, admin, restricted
    required_roles: Mapped[Optional[list[str]]] = mapped_column(ARRAY(String), nullable=True)
    jurisdiction: Mapped[str] = mapped_column(
        String(50), default="international"
    )  # international, state:IL, lodge:1234
    citation_format: Mapped[str] = mapped_column(
        String(20), default="section"
    )  # section, article, page, rule, module
    status: Mapped[str] = mapped_column(
        String(20), default="draft", index=True
    )  # draft, processing, active, superseded, archived, error
    created_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    created_by_user: Mapped["User"] = relationship(
        back_populates="uploaded_documents", foreign_keys=[created_by]
    )
    versions: Mapped[list["DocumentVersion"]] = relationship(
        back_populates="document", lazy="selectin",
        order_by="DocumentVersion.version_number.desc()"
    )
    sections: Mapped[list["Section"]] = relationship(back_populates="document")
    parent_document_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("documents.id"), nullable=True
    )  # For policy updates referencing parent

    def __repr__(self) -> str:
        return f"<Document {self.title}>"


class DocumentVersion(Base):
    __tablename__ = "document_versions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    s3_key: Mapped[str] = mapped_column(
        String(1000), nullable=False
    )  # Path in S3/MinIO
    page_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    content_hash: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True
    )  # SHA-256 of raw file
    uploaded_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    effective_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    is_current: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    status: Mapped[str] = mapped_column(
        String(20), default="received"
    )  # received, processing, active, error
    ocr_applied: Mapped[bool] = mapped_column(Boolean, default=False)
    ocr_engine: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    ocr_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    changelog: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    document: Mapped["Document"] = relationship(back_populates="versions")
    sections: Mapped[list["Section"]] = relationship(
        back_populates="version", lazy="selectin"
    )
    chunks: Mapped[list["Chunk"]] = relationship(back_populates="version")

    __table_args__ = (
        UniqueConstraint("document_id", "version_number", name="uq_doc_version"),
    )

    def __repr__(self) -> str:
        return f"<DocumentVersion {self.document_id} v{self.version_number}>"


# ── Content ──────────────────────────────────────────────────

class Section(Base):
    __tablename__ = "sections"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("document_versions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    parent_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("sections.id", ondelete="SET NULL"), nullable=True
    )
    section_number: Mapped[str] = mapped_column(
        String(100), nullable=False
    )  # "24.3(a)" — canonical form
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    level: Mapped[int] = mapped_column(
        Integer, nullable=False
    )  # 1=chapter, 2=article, 3=section, 4=subsection, 5=paragraph
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    page_start: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    page_end: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    hierarchy_path: Mapped[str] = mapped_column(
        String(1000), nullable=False
    )  # "Ch 2 > Art V > §24.3 > §24.3(a)"

    # Relationships
    document: Mapped["Document"] = relationship(back_populates="sections")
    version: Mapped["DocumentVersion"] = relationship(back_populates="sections")
    parent: Mapped[Optional["Section"]] = relationship(
        remote_side="Section.id", back_populates="children"
    )
    children: Mapped[list["Section"]] = relationship(back_populates="parent")
    chunks: Mapped[list["Chunk"]] = relationship(
        back_populates="section", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<Section {self.section_number}: {self.title}>"


class Chunk(Base):
    __tablename__ = "chunks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    section_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sections.id", ondelete="CASCADE"), nullable=False, index=True
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("document_versions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    total_chunks_in_section: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    content_text: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True
    )  # SHA-256 for dedup
    token_count: Mapped[int] = mapped_column(Integer, nullable=False)
    page_start: Mapped[int] = mapped_column(Integer, nullable=False)
    page_end: Mapped[int] = mapped_column(Integer, nullable=False)
    hierarchy_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    citation_header: Mapped[str] = mapped_column(
        Text, nullable=False
    )  # Pre-formatted citation for LLM context
    is_superseded: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, index=True
    )
    embedding_reused: Mapped[bool] = mapped_column(
        Boolean, default=False
    )  # Was embedding from previous version reused?
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    section: Mapped["Section"] = relationship(back_populates="chunks")
    version: Mapped["DocumentVersion"] = relationship(back_populates="chunks")
    embedding_variants: Mapped[list["ChunkEmbedding"]] = relationship(
        back_populates="chunk", lazy="selectin"
    )

    __table_args__ = (
        UniqueConstraint("version_id", "section_id", "chunk_index", name="uq_chunk"),
    )

    def __repr__(self) -> str:
        return f"<Chunk {self.section.section_number if self.section else '?'} [{self.chunk_index}]>"


class ChunkEmbedding(Base):
    """Multi-variant embeddings per chunk (full, title, summary)."""

    __tablename__ = "chunk_embeddings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    chunk_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("chunks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    variant: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # 'full', 'title', 'summary'
    embedding: Mapped[Any] = mapped_column(Vector(3072), nullable=True)
    weight: Mapped[float] = mapped_column(Float, default=1.0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    chunk: Mapped["Chunk"] = relationship(back_populates="embedding_variants")

    def __repr__(self) -> str:
        return f"<ChunkEmbedding {self.chunk_id} [{self.variant}]>"


# ── Analytics ────────────────────────────────────────────────

class QueryLog(Base):
    __tablename__ = "query_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    session_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    response_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    confidence_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    confidence_level: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True
    )  # HIGH, MEDIUM, LOW, INCONCLUSIVE
    citations_data: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    chunk_ids_retrieved: Mapped[Optional[list[str]]] = mapped_column(
        ARRAY(String), nullable=True
    )
    retrieval_latency_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    generation_latency_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    model_used: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    feedback: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True
    )  # helpful, not_helpful, flagged
    feedback_detail: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    user: Mapped[Optional["User"]] = relationship(back_populates="query_logs")

    def __repr__(self) -> str:
        return f"<QueryLog {self.id[:8]}...>"
