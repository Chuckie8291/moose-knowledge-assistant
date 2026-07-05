"""Tests for the document classifier."""

import pytest

from app.core.ingestion.classifier import DocumentClassifier


class TestDocumentClassifier:
    """Test document classification logic."""

    def setup_method(self):
        self.classifier = DocumentClassifier()

    def test_classify_general_laws_by_filename(self):
        """Test classification by filename heuristics."""
        result = self.classifier.classify(
            preview_text="",
            filename="General_Laws_2025.pdf",
        )
        assert result.doc_type == "general_laws"
        assert result.tier == 1
        assert result.confidence >= 0.85

    def test_classify_officer_handbook_by_filename(self):
        """Test classification of officer handbook."""
        result = self.classifier.classify(
            preview_text="",
            filename="Officer_and_Committeemen_Handbook_2023.pdf",
        )
        assert result.doc_type == "officer_handbook"
        assert result.tier == 3

    def test_classify_by_content_keywords(self):
        """Test content-based classification."""
        result = self.classifier.classify(
            preview_text=(
                "The Governor shall have full authority over all employees. "
                "The duties and responsibilities of the Governor include "
                "presiding over meetings and overseeing operations. "
                "Social quarters rules govern bar operations and bartender duties."
            ),
            filename="unknown.pdf",
        )
        assert result.doc_type in ("general_laws", "officer_handbook", "social_quarters_rules")

    def test_classify_unknown_document(self):
        """Test classification of unknown content."""
        result = self.classifier.classify(
            preview_text="This is a random document about cooking recipes.",
            filename="unknown.pdf",
        )
        assert result.doc_type == "other"
        assert result.confidence < 0.80
        assert result.needs_admin_review is True

    def test_detect_jurisdiction(self):
        """Test jurisdiction detection."""
        result = self.classifier.classify(
            preview_text="The bylaws of Lodge #1234 in Springfield, Illinois...",
            filename="lodge_bylaws.pdf",
        )
        assert "illinois" in result.detected_jurisdiction.lower() or \
               "lodge" in result.detected_jurisdiction.lower()
