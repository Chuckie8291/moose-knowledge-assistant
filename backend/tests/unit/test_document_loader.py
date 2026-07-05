"""Tests for the document loader."""

import pytest
from pathlib import Path

from app.core.ingestion.document_loader import DocumentLoader


class TestDocumentLoader:
    """Test loading various document formats."""

    def test_load_text_file(self, tmp_path):
        """Test loading a plain text file."""
        file_path = tmp_path / "test.txt"
        file_path.write_text("This is a test document.")

        loader = DocumentLoader()
        result = loader.load(str(file_path))

        assert result.total_pages == 1
        assert result.total_chars > 0
        assert result.is_digital is True
        assert result.file_ext == ".txt"
        assert len(result.content_hash) == 64  # SHA-256

    def test_load_preview(self, tmp_path):
        """Test preview extraction for classification."""
        file_path = tmp_path / "preview.txt"
        file_path.write_text("Page 1 content.\n\nPage 2 content.\n\nPage 3 content.")

        loader = DocumentLoader()
        preview = loader.load_preview(str(file_path))

        assert len(preview) > 0
        assert "Page 1" in preview

    def test_unsupported_format(self, tmp_path):
        """Test that unsupported formats raise an error."""
        file_path = tmp_path / "test.xyz"
        file_path.write_text("content")

        loader = DocumentLoader()
        with pytest.raises(ValueError, match="Unsupported"):
            loader.load(str(file_path))

    def test_content_hash_consistency(self, tmp_path):
        """Test that content hash is deterministic."""
        file_path = tmp_path / "hash_test.txt"
        file_path.write_text("Same content")

        loader = DocumentLoader()
        result1 = loader.load(str(file_path))
        result2 = loader.load(str(file_path))

        assert result1.content_hash == result2.content_hash
