"""
Embedder — Generates vector embeddings for chunks.

Uses OpenAI text-embedding-3-large (3072-dim) as primary.
Supports content-hash caching to skip re-embedding unchanged chunks.
"""

from __future__ import annotations

import hashlib
import math
from typing import Optional

from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import settings
from app.utils.logging import get_logger

logger = get_logger(__name__)


class EmbeddingGenerator:
    """Generate embeddings with batching, caching, and retry."""

    def __init__(self):
        self.model = settings.openai_embedding_model
        self.dimensions = settings.openai_embedding_dimensions
        self.batch_size = settings.openai_embedding_batch_size

    def generate(
        self,
        chunks: list["ChunkData"],
        previous_version_id: Optional[str] = None,
    ) -> list["ChunkData"]:
        """
        Generate embeddings for chunks.

        Args:
            chunks: ChunkData objects to embed.
            previous_version_id: If provided, check for unchanged chunks to reuse embeddings.

        Returns:
            Same chunks with embeddings populated.
        """
        from openai import OpenAI

        client = OpenAI(api_key=settings.openai_api_key)

        chunks_needing_embed = []
        for chunk in chunks:
            content_hash = chunk.metadata.get("content_hash", "")
            if self._try_reuse_embedding(chunk, previous_version_id):
                chunk.metadata["embedding_reused"] = True
            else:
                chunks_needing_embed.append(chunk)

        if not chunks_needing_embed:
            logger.info("All chunks reused existing embeddings — skipping generation")
            return chunks

        logger.info(
            "Generating embeddings for %d chunks (batch size %d)",
            len(chunks_needing_embed), self.batch_size
        )

        for i in range(0, len(chunks_needing_embed), self.batch_size):
            batch = chunks_needing_embed[i:i + self.batch_size]
            texts = [chunk.content_text for chunk in batch]

            try:
                embeddings = self._call_openai(client, texts)
            except Exception as e:
                logger.error("Embedding API call failed: %s", e)
                # Mark chunks as needing retry
                for chunk in batch:
                    chunk.metadata["embedding_error"] = str(e)
                continue

            for chunk, embedding in zip(batch, embeddings):
                chunk.metadata["embedding"] = embedding
                chunk.metadata["embedding_model"] = self.model
                chunk.metadata["embedding_dimensions"] = self.dimensions

        return chunks

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
    )
    def _call_openai(self, client, texts: list[str]) -> list[list[float]]:
        """Call OpenAI embeddings API with retry."""
        response = client.embeddings.create(
            model=self.model,
            input=texts,
            dimensions=self.dimensions,
        )
        return [item.embedding for item in response.data]

    def _try_reuse_embedding(
        self, chunk: "ChunkData", previous_version_id: Optional[str]
    ) -> bool:
        """
        Check if this chunk's embedding can be reused from a previous version.
        For now, this is a stub — full implementation requires database access.
        """
        # Stub: always return False (generate new embeddings)
        # Full implementation would:
        # 1. Query DB for chunks with same content_hash from previous_version_id
        # 2. If found, copy the embedding vector
        return False

    def generate_single(self, text: str) -> list[float]:
        """Generate embedding for a single text (used for query embedding)."""
        from openai import OpenAI
        client = OpenAI(api_key=settings.openai_api_key)
        response = client.embeddings.create(
            model=self.model,
            input=[text],
            dimensions=self.dimensions,
        )
        return response.data[0].embedding


# ── Embedding Quality Checks ─────────────────────────────────

def check_embedding_quality(embedding: list[float]) -> Optional[str]:
    """
    Run quality checks on a generated embedding.
    Returns None if OK, or an error description string.
    """
    if not embedding:
        return "Embedding is empty"

    # Zero-vector check
    if all(v == 0.0 for v in embedding):
        return "All dimensions are zero (API error)"

    # Dimension check
    if len(embedding) != settings.openai_embedding_dimensions:
        return f"Wrong dimensions: expected {settings.openai_embedding_dimensions}, got {len(embedding)}"

    # Magnitude check
    magnitude = math.sqrt(sum(v ** 2 for v in embedding))
    if magnitude < 0.01:
        return f"Embedding magnitude too low: {magnitude:.6f}"
    if magnitude > 100:
        return f"Embedding magnitude too high: {magnitude:.1f}"

    return None


# ── Text Preparation for Embedding ───────────────────────────

def prepare_embedding_text(chunk: "ChunkData") -> str:
    """
    Prepare text for optimal embedding quality.
    Includes structural metadata to improve retrieval of section-specific queries.

    For example, "what does section 24.3 say" will match even when
    "24.3" doesn't appear in the body text, because we include it in
    the embedded text.
    """
    parts = []

    # Include document context
    if chunk.document_short_title:
        parts.append(f"Document: {chunk.document_short_title}.")

    # Include section identifier — CRITICAL for exact section queries
    parts.append(f"Section: {chunk.section_number}.")

    if chunk.section_title:
        parts.append(f"Title: {chunk.section_title}.")

    if chunk.hierarchy_path:
        parts.append(f"Hierarchy: {chunk.hierarchy_path}.")

    # Include the actual content
    parts.append(f"Text: {chunk.content_text}")

    text = " ".join(parts)

    # Normalize: collapse whitespace
    import re
    text = re.sub(r'\s+', ' ', text).strip()

    return text
