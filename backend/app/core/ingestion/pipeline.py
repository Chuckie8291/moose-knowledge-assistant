"""
Ingestion Pipeline Orchestrator — Coordinates the full 9-stage ingestion pipeline.

Stages:
  1. Load — Read raw file, extract text/images
  2. Classify — Auto-detect document type and tier
  3. OCR Decision — Determine if OCR is needed
  4. OCR — Run OCR on scanned pages
  5. Structure — Extract section hierarchy
  6. Chunk — Split into retrieval-optimized chunks
  7. Embed — Generate vector embeddings
  8. Index — Store in PostgreSQL + Elasticsearch
  9. Validate — Quality checks before activation
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date
from typing import Optional

from app.config import settings
from app.core.ingestion.document_loader import DocumentLoader, LoadedDocument
from app.core.ingestion.classifier import DocumentClassifier, ClassificationResult
from app.core.ingestion.ocr_engine import (
    OCRDecisionEngine, OCRDecision, get_ocr_engine, NoOCREngine
)
from app.core.ingestion.structure_extractor import (
    get_structure_extractor, SectionTree, SectionNode
)
from app.core.ingestion.chunker import get_chunker, ChunkData
from app.core.ingestion.embedder import EmbeddingGenerator, check_embedding_quality
from app.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class IngestionResult:
    """Complete result of document ingestion."""
    document_id: str
    version_id: str
    doc_type: str
    tier: int
    total_pages: int
    total_sections: int
    total_chunks: int
    ocr_applied: bool
    ocr_engine: Optional[str]
    ocr_confidence: Optional[float]
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    status: str = "active"  # active | error


class IngestionPipeline:
    """
    Orchestrates the full document ingestion from raw file to searchable chunks.

    Usage:
        pipeline = IngestionPipeline()
        result = await pipeline.ingest(
            file_path="/path/to/General_Laws_2025.pdf",
            document_id=uuid4(),
            version_id=uuid4(),
            metadata={"title": "General Laws of the Moose Fraternity"},
        )
    """

    def __init__(self):
        self.loader = DocumentLoader()
        self.classifier = DocumentClassifier()
        self.ocr_decision_engine = OCRDecisionEngine()
        self.embedder = EmbeddingGenerator()

    def ingest(
        self,
        file_path: str,
        document_id: str = "",
        version_id: str = "",
        metadata: Optional[dict] = None,
    ) -> IngestionResult:
        """
        Run the full ingestion pipeline.

        Args:
            file_path: Path to the raw document file.
            document_id: UUID of the Document record (created by caller).
            version_id: UUID of the DocumentVersion record (created by caller).
            metadata: Optional admin-provided metadata (title, doc_type override, etc.).

        Returns:
            IngestionResult with summary statistics.
        """
        metadata = metadata or {}
        result = IngestionResult(
            document_id=document_id or str(uuid.uuid4()),
            version_id=version_id or str(uuid.uuid4()),
            doc_type="other",
            tier=12,
            total_pages=0,
            total_sections=0,
            total_chunks=0,
            ocr_applied=False,
            ocr_engine=None,
            ocr_confidence=None,
        )

        try:
            # ── STAGE 1: LOAD ────────────────────────────────
            logger.info("Stage 1/9: Loading document from %s", file_path)
            loaded = self.loader.load(file_path)
            result.total_pages = loaded.total_pages
            logger.info(
                "Loaded: %d pages, %d characters, digital=%s",
                loaded.total_pages, loaded.total_chars, loaded.is_digital
            )

            # ── STAGE 2: CLASSIFY ─────────────────────────────
            logger.info("Stage 2/9: Classifying document")
            if metadata.get("doc_type"):
                # Admin override — trust it
                from app.core.ingestion.classifier import DOC_TYPES
                type_info = DOC_TYPES.get(metadata["doc_type"], DOC_TYPES["other"])
                classification = ClassificationResult(
                    doc_type=metadata["doc_type"],
                    tier=type_info["tier"],
                    category=type_info["category"],
                    citation_format=type_info["citation_format"],
                    label=type_info["label"],
                    confidence=1.0,
                    needs_admin_review=False,
                    detected_jurisdiction="international",
                )
            else:
                preview = self.loader.load_preview(file_path)
                classification = self.classifier.classify(
                    preview_text=preview,
                    filename=file_path,
                )
            result.doc_type = classification.doc_type
            result.tier = classification.tier
            logger.info(
                "Classified: %s (Tier %d, confidence=%.0f%%)",
                classification.label, classification.tier,
                classification.confidence * 100
            )

            # ── STAGE 3: OCR DECISION ─────────────────────────
            logger.info("Stage 3/9: OCR decision")
            ocr_decision = self.ocr_decision_engine.decide(loaded)
            result.ocr_applied = ocr_decision.needs_ocr
            result.ocr_engine = ocr_decision.engine
            logger.info("OCR decision: %s — %s", ocr_decision.engine, ocr_decision.reason)

            # ── STAGE 4: OCR ──────────────────────────────────
            if ocr_decision.needs_ocr:
                logger.info("Stage 4/9: Running OCR")
                engine = get_ocr_engine(ocr_decision.engine)

                if ocr_decision.engine == "mixed":
                    # OCR only scanned pages
                    for idx in ocr_decision.scanned_page_indices:
                        if idx < len(loaded.pages):
                            page = loaded.pages[idx]
                            ocr_result = engine.process_page(
                                page.image_bytes, page.page_number
                            )
                            page.text = ocr_result.text
                            page.char_count = len(ocr_result.text)
                else:
                    # OCR all pages
                    for page in loaded.pages:
                        if page.image_bytes:
                            ocr_result = engine.process_page(
                                page.image_bytes, page.page_number
                            )
                            page.text = ocr_result.text
                            page.char_count = len(ocr_result.text)

                # Recalculate total chars
                loaded.total_chars = sum(p.char_count for p in loaded.pages)

                # Calculate aggregate OCR confidence
                # (simplified — in production, track per-page)
                result.ocr_confidence = 0.90  # Placeholder
            else:
                logger.info("Stage 4/9: Skipping OCR (digital document)")

            # ── STAGE 5: STRUCTURE EXTRACTION ─────────────────
            logger.info("Stage 5/9: Extracting document structure")
            full_text = "\n\n".join(p.text for p in loaded.pages)

            # Build page map: character position → page number
            page_map = self._build_page_map(loaded.pages)

            extractor = get_structure_extractor(classification.doc_type)
            tree = extractor.extract(full_text, page_map)
            result.total_sections = len(tree.all_sections())
            logger.info(
                "Extracted: %d sections (%d leaf sections with content)",
                result.total_sections, len(tree.leaf_sections())
            )

            # ── STAGE 6: CHUNK ────────────────────────────────
            logger.info("Stage 6/9: Chunking document")
            title = metadata.get("title", classification.label)
            chunker = get_chunker(classification.doc_type)
            chunk_datas = chunker.chunk(
                tree=tree,
                doc_short_title=title,
                doc_tier=classification.tier,
                effective_date=str(metadata.get("effective_date", date.today())),
            )
            result.total_chunks = len(chunk_datas)
            logger.info("Created: %d chunks", result.total_chunks)

            # ── STAGE 7: EMBED ────────────────────────────────
            logger.info("Stage 7/9: Generating embeddings")
            chunk_datas = self.embedder.generate(chunk_datas)

            # Quality check sample
            for chunk in chunk_datas[:3]:
                embedding = chunk.metadata.get("embedding")
                if embedding:
                    quality_issue = check_embedding_quality(embedding)
                    if quality_issue:
                        result.warnings.append(
                            f"Embedding quality issue in chunk {chunk.chunk_index}: {quality_issue}"
                        )
            logger.info("Embeddings generated for %d chunks", result.total_chunks)

            # ── STAGE 8: INDEX ────────────────────────────────
            logger.info("Stage 8/9: Indexing chunks (stub — requires DB + ES)")
            # In production, this would:
            #   a. Insert sections into PostgreSQL
            #   b. Insert chunks with embeddings into PostgreSQL (pgvector)
            #   c. Index chunks into Elasticsearch
            # For now, we return the chunk data for the caller to persist.
            result.metadata = {
                "chunks": chunk_datas,
                "classification": classification,
                "section_tree": tree,
            }

            # ── STAGE 9: VALIDATE ─────────────────────────────
            logger.info("Stage 9/9: Validating ingestion")
            validation_errors = self._validate(chunk_datas, tree, classification)
            if validation_errors:
                result.errors.extend(validation_errors)
                result.status = "error"
                logger.warning("Validation found %d errors", len(validation_errors))
            else:
                logger.info("Validation passed — document is ready")

        except Exception as e:
            logger.exception("Ingestion failed: %s", e)
            result.errors.append(str(e))
            result.status = "error"

        return result

    # ── Helpers ───────────────────────────────────────────────

    @staticmethod
    def _build_page_map(pages: list) -> dict[int, int]:
        """Map character positions to page numbers."""
        page_map = {}
        char_pos = 0
        for page in pages:
            page_map[char_pos] = page.page_number
            char_pos += len(page.text) + 2  # +2 for \n\n separator
        return page_map

    @staticmethod
    def _validate(
        chunks: list[ChunkData],
        tree: SectionTree,
        classification: ClassificationResult,
    ) -> list[str]:
        """Run quality validation checks."""
        errors = []

        # 1. Every leaf section must have at least one chunk
        leaf_sections_seen = set()
        for chunk in chunks:
            leaf_sections_seen.add(chunk.section_number)

        for section in tree.leaf_sections():
            if section.section_number not in leaf_sections_seen:
                errors.append(
                    f"Section {section.section_number} has no chunks"
                )

        # 2. No empty chunks
        empty_chunks = [c for c in chunks if not c.content_text.strip()]
        if empty_chunks:
            errors.append(f"{len(empty_chunks)} chunks have no content")

        # 3. Citation headers present
        no_citation = [c for c in chunks if not c.citation_header]
        if no_citation:
            errors.append(f"{len(no_citation)} chunks lack citation headers")

        # 4. Minimum chunk count
        if len(chunks) == 0:
            errors.append("No chunks were created")

        return errors
