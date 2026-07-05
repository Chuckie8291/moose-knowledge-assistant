"""Tests for structure extraction."""

import pytest

from app.core.ingestion.structure_extractor import (
    LegalStructureExtractor,
    HandbookStructureExtractor,
    RitualStructureExtractor,
    SectionTree,
)


class TestLegalStructureExtractor:
    """Test structure extraction from legal documents."""

    def test_extract_chapters_and_sections(self, sample_legal_text):
        """Test that chapters, articles, sections, and subsections are detected."""
        extractor = LegalStructureExtractor()
        page_map = {0: 1}
        tree = extractor.extract(sample_legal_text, page_map)

        sections = tree.all_sections()
        assert len(sections) >= 4  # Chapter, Article, Section, at least one subsection

    def test_hierarchy_path(self, sample_legal_text):
        """Test that hierarchy paths are built correctly."""
        extractor = LegalStructureExtractor()
        page_map = {0: 1}
        tree = extractor.extract(sample_legal_text, page_map)

        # Find a subsection
        leaf_sections = tree.leaf_sections()
        assert len(leaf_sections) > 0

        for section in leaf_sections:
            path = section.hierarchy_path
            assert ">" in path or section.level > 1  # Non-root sections have hierarchy

    def test_empty_document(self):
        """Test that empty documents produce a single section."""
        extractor = LegalStructureExtractor()
        tree = extractor.extract("", {0: 1})

        assert len(tree.root_sections) == 1
        assert tree.root_sections[0].title == "Full Document"


class TestHandbookStructureExtractor:
    """Test structure extraction from officer handbooks."""

    def test_extract_officer_sections(self, sample_handbook_text):
        """Test that officer names are detected as sections."""
        extractor = HandbookStructureExtractor()
        page_map = {0: 1}
        tree = extractor.extract(sample_handbook_text, page_map)

        sections = tree.all_sections()
        section_titles = [s.title for s in sections]

        # Should detect Governor, Junior Governor, Treasurer
        assert any("Governor" in t for t in section_titles)
        assert any("Treasurer" in t for t in section_titles)


class TestRitualStructureExtractor:
    """Test structure extraction from ritual documents."""

    def test_extract_ceremonies(self, sample_ritual_text):
        """Test that ceremonies and speaker blocks are detected."""
        extractor = RitualStructureExtractor()
        page_map = {0: 1}
        tree = extractor.extract(sample_ritual_text, page_map)

        sections = tree.all_sections()
        section_titles = [s.title for s in sections]

        # Should detect OPENING CEREMONY, 9 O'CLOCK CEREMONY
        assert any("OPENING" in t for t in section_titles)
        assert any("9" in t or "O'CLOCK" in t for t in section_titles)
