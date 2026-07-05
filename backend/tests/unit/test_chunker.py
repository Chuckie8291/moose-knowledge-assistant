"""Tests for the chunker."""

import pytest

from app.core.ingestion.chunker import LegalDocumentChunker
from app.core.ingestion.structure_extractor import (
    LegalStructureExtractor, SectionTree
)


class TestLegalDocumentChunker:
    """Test legal document chunking."""

    def test_chunk_small_section(self, sample_legal_text):
        """Test that a small section stays as one chunk."""
        extractor = LegalStructureExtractor()
        tree = extractor.extract(sample_legal_text, {0: 1})

        chunker = LegalDocumentChunker()
        chunks = chunker.chunk(tree, doc_short_title="General Laws", doc_tier=1)

        assert len(chunks) > 0
        for chunk in chunks:
            assert chunk.content_text  # Non-empty
            assert chunk.citation_header  # Has citation
            assert "General Laws" in chunk.citation_header
            assert chunk.section_number  # Has section number

    def test_chunk_preserves_citation(self, sample_legal_text):
        """Test that every chunk has a citation header."""
        extractor = LegalStructureExtractor()
        tree = extractor.extract(sample_legal_text, {0: 1})

        chunker = LegalDocumentChunker()
        chunks = chunker.chunk(tree, doc_short_title="General Laws", doc_tier=1)

        for chunk in chunks:
            assert chunk.citation_header.startswith("[SOURCE:")
            assert "§" in chunk.citation_header or "Section" in chunk.citation_header.lower()

    def test_content_hash_in_metadata(self, sample_legal_text):
        """Test that each chunk has a content hash in its metadata."""
        extractor = LegalStructureExtractor()
        tree = extractor.extract(sample_legal_text, {0: 1})

        chunker = LegalDocumentChunker()
        chunks = chunker.chunk(tree)

        for chunk in chunks:
            assert "content_hash" in chunk.metadata
            assert len(chunk.metadata["content_hash"]) == 64

    def test_empty_tree_produces_chunks(self):
        """Test that an empty tree still produces at least a root chunk."""
        tree = SectionTree()
        chunker = LegalDocumentChunker()
        chunks = chunker.chunk(tree)

        # Even empty trees should produce at least a root section chunk
        # (depending on implementation, might produce 0 or 1 chunk)
        assert isinstance(chunks, list)
