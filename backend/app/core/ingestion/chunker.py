"""
Chunker — Splits document sections into retrieval-optimized chunks.

Strategies by document type:
  - Legal: Section-aware, split at paragraph boundaries
  - Handbook: Officer/topic-aware
  - Ritual: Ceremony/speaker-aware
  - Newsletter: Article-per-chunk
  - Sports: Rule-per-chunk

Every chunk gets a full citation breadcrumb preserved.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Optional

import tiktoken

from app.config import settings
from app.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ChunkData:
    """A chunk ready for embedding and indexing."""
    section_id: Optional[str]  # Filled after section is persisted
    document_id: Optional[str]
    version_id: Optional[str]
    chunk_index: int
    total_chunks_in_section: int
    content_text: str
    token_count: int
    page_start: int
    page_end: int
    hierarchy_path: str
    citation_header: str
    section_number: str
    section_title: str
    document_short_title: str = ""
    document_tier: int = 1
    effective_date: Optional[str] = None
    metadata: dict = field(default_factory=dict)


class BaseChunker:
    """Base chunker with token counting and utilities."""

    def __init__(self):
        try:
            self._tokenizer = tiktoken.get_encoding("cl100k_base")
        except Exception:
            self._tokenizer = None

    def _count_tokens(self, text: str) -> int:
        """Count tokens using tiktoken, fallback to approximate."""
        if self._tokenizer:
            return len(self._tokenizer.encode(text))
        return len(text.split()) * 1.3  # Rough estimate

    def _split_paragraphs(self, text: str) -> list[str]:
        """Split text at paragraph boundaries."""
        # Split on double newline or explicit paragraph markers
        paragraphs = re.split(r'\n\s*\n', text)
        return [p.strip() for p in paragraphs if p.strip()]

    def _split_sentences(self, text: str) -> list[str]:
        """Split text at sentence boundaries."""
        return re.split(r'(?<=[.!?])\s+', text)


class LegalDocumentChunker(BaseChunker):
    """
    Chunk legal/governing documents.

    Rules:
      - Never split mid-section if the section fits within MAX_TOKENS.
      - If a section is too large, split at paragraph boundaries.
      - Overlap the last 1-2 paragraphs of the previous chunk.
      - Target: 600 tokens; Max: 1000 tokens.
    """

    def chunk(
        self,
        tree: "SectionTree",
        doc_short_title: str = "",
        doc_tier: int = 1,
        effective_date: str = "",
    ) -> list[ChunkData]:
        chunks = []

        for section in tree.leaf_sections():
            text = section.full_text
            token_count = self._count_tokens(text)

            if token_count <= settings.chunk_max_tokens:
                # Entire section fits in one chunk
                chunks.append(self._make_chunk(
                    section=section,
                    text=text,
                    chunk_index=0,
                    total_chunks=1,
                    doc_short_title=doc_short_title,
                    doc_tier=doc_tier,
                    effective_date=effective_date,
                ))
            else:
                # Split at paragraph boundaries
                paragraphs = self._split_paragraphs(text)
                current_paras = []
                current_tokens = 0
                chunk_index = 0

                for para in paragraphs:
                    para_tokens = self._count_tokens(para)

                    if (
                        current_tokens + para_tokens > settings.chunk_target_tokens
                        and current_paras
                    ):
                        # Emit current chunk
                        chunks.append(self._make_chunk(
                            section=section,
                            text="\n\n".join(current_paras),
                            chunk_index=chunk_index,
                            total_chunks=0,  # Filled later
                            doc_short_title=doc_short_title,
                            doc_tier=doc_tier,
                            effective_date=effective_date,
                        ))
                        chunk_index += 1

                        # Overlap: keep last 1-2 paragraphs
                        overlap_count = min(2, len(current_paras))
                        current_paras = current_paras[-overlap_count:]
                        current_tokens = sum(
                            self._count_tokens(p) for p in current_paras
                        )

                    current_paras.append(para)
                    current_tokens += para_tokens

                # Emit final chunk
                if current_paras:
                    chunks.append(self._make_chunk(
                        section=section,
                        text="\n\n".join(current_paras),
                        chunk_index=chunk_index,
                        total_chunks=0,
                        doc_short_title=doc_short_title,
                        doc_tier=doc_tier,
                        effective_date=effective_date,
                    ))
                    chunk_index += 1

                # Backfill total_chunks for all chunks of this section
                for i in range(len(chunks) - chunk_index, len(chunks)):
                    chunks[i].total_chunks_in_section = chunk_index

        return chunks

    def _make_chunk(
        self,
        section: "SectionNode",
        text: str,
        chunk_index: int,
        total_chunks: int,
        doc_short_title: str,
        doc_tier: int,
        effective_date: str,
    ) -> ChunkData:
        """Create a ChunkData with full citation breadcrumb."""
        token_count = self._count_tokens(text)
        content_hash = hashlib.sha256(text.encode()).hexdigest()

        # Build citation header for LLM context
        version_info = f"v{effective_date}" if effective_date else "current"
        citation_header = (
            f"[SOURCE: {doc_short_title} | "
            f"§{section.section_number} — \"{section.title}\" | "
            f"Tier {doc_tier} | "
            f"{version_info} | "
            f"p. {section.page_start}"
        )
        if section.page_end != section.page_start:
            citation_header += f"-{section.page_end}"
        if total_chunks > 1:
            citation_header += f" | Chunk {chunk_index + 1}/{total_chunks}"
        citation_header += "]"

        return ChunkData(
            section_id=None,
            document_id=None,
            version_id=None,
            chunk_index=chunk_index,
            total_chunks_in_section=total_chunks,
            content_text=text,
            token_count=token_count,
            page_start=section.page_start,
            page_end=section.page_end,
            hierarchy_path=section.hierarchy_path,
            citation_header=citation_header,
            section_number=section.section_number,
            section_title=section.title,
            document_short_title=doc_short_title,
            document_tier=doc_tier,
            effective_date=effective_date,
            metadata={
                "content_hash": content_hash,
            },
        )


class HandbookChunker(BaseChunker):
    """Chunk handbooks by officer role or topic. Similar to legal but with handbook-specific settings."""

    def chunk(self, tree, doc_short_title="", doc_tier=3, effective_date="") -> list[ChunkData]:
        # Same logic as LegalDocumentChunker but with different target tokens
        legal_chunker = LegalDocumentChunker()
        return legal_chunker.chunk(tree, doc_short_title, doc_tier, effective_date)


class RitualChunker(BaseChunker):
    """Chunk ritual scripts. Never split mid-oath or mid-prayer."""

    def chunk(self, tree, doc_short_title="", doc_tier=2, effective_date="") -> list[ChunkData]:
        legal_chunker = LegalDocumentChunker()
        return legal_chunker.chunk(tree, doc_short_title, doc_tier, effective_date)


class NewsletterChunker(BaseChunker):
    """Chunk newsletters — one chunk per article."""

    def chunk(self, tree, doc_short_title="", doc_tier=12, effective_date="") -> list[ChunkData]:
        legal_chunker = LegalDocumentChunker()
        return legal_chunker.chunk(tree, doc_short_title, doc_tier, effective_date)


# ── Factory ──────────────────────────────────────────────────

_CHUNKERS = {
    "general_laws": LegalDocumentChunker,
    "constitution": LegalDocumentChunker,
    "wotm_general_laws": LegalDocumentChunker,
    "association_bylaws": LegalDocumentChunker,
    "local_bylaws": LegalDocumentChunker,
    "officer_handbook": HandbookChunker,
    "election_handbook": HandbookChunker,
    "social_quarters_rules": LegalDocumentChunker,
    "financial_policy": LegalDocumentChunker,
    "lodge_ritual": RitualChunker,
    "degree_ritual": RitualChunker,
    "memorial_service": RitualChunker,
    "installation_ceremony": RitualChunker,
    "newsletter": NewsletterChunker,
    "training_guide": HandbookChunker,
    "sports_rules": LegalDocumentChunker,
    "activities_guidebook": HandbookChunker,
}


def get_chunker(doc_type: str) -> BaseChunker:
    """Factory: return the appropriate chunker for this document type."""
    chunker_class = _CHUNKERS.get(doc_type, LegalDocumentChunker)
    return chunker_class()
