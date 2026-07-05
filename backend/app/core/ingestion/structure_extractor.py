"""
Structure Extractor — Extracts hierarchical section structure from documents.

Different document types have different structures:
  - Legal Documents: Chapter > Article > Section > Subsection > Paragraph
  - Handbooks: Part > Officer Role > Topic
  - Ritual: Ceremony > Speaker Block > Action
  - Newsletters: Issue > Article
  - Sports Rules: Sport > Rule > Sub-rule

The extractor produces a SectionTree that feeds into the chunker.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from app.utils.logging import get_logger

logger = get_logger(__name__)


# ── Data Structures ──────────────────────────────────────────

class SectionLevel(Enum):
    CHAPTER = 1
    ARTICLE = 2
    SECTION = 3
    SUBSECTION = 4
    PARAGRAPH = 5
    SUBPARAGRAPH = 6


@dataclass
class TextLine:
    """A single line of text with formatting metadata."""
    text: str
    page_number: int
    line_number: int
    is_bold: bool = False
    is_italic: bool = False
    font_size: float = 10.0
    is_all_caps: bool = False

    def __post_init__(self):
        self.is_all_caps = (
            self.text.isupper() and len(self.text) > 3 and not self.text.isdigit()
        )


@dataclass
class DetectedSection:
    """A detected section heading."""
    level: int                        # 1=chapter, 2=article, etc.
    level_name: str                   # "chapter", "section", etc.
    number: str                       # "24.3(a)" or "V"
    title: str                        # "Authority Over Bar Operations"
    page_number: int
    line_number: int
    confidence: float                 # 0.0 to 1.0


@dataclass
class SectionNode:
    """A node in the section tree."""
    section_number: str
    title: str
    level: int
    page_start: int
    page_end: int
    parent: Optional["SectionNode"] = None
    children: list["SectionNode"] = field(default_factory=list)
    content_lines: list[TextLine] = field(default_factory=list)
    sort_order: int = 0

    @property
    def full_text(self) -> str:
        """All text content within this section."""
        return "\n".join(line.text for line in self.content_lines)

    @property
    def hierarchy_path(self) -> str:
        """Breadcrumb path: 'Ch 2 > Art V > §24 > §24.3 > §24.3(a)'."""
        parts = []
        current: Optional[SectionNode] = self
        while current:
            prefix = {
                1: "Ch",
                2: "Art",
                3: "§",
                4: "§",
                5: "¶",
                6: "¶",
            }.get(current.level, "§")
            parts.append(f"{prefix} {current.section_number}")
            current = current.parent
        return " > ".join(reversed(parts))

    @property
    def is_leaf(self) -> bool:
        return len(self.children) == 0


class SectionTree:
    """The complete section hierarchy of a document."""

    def __init__(self):
        self.root_sections: list[SectionNode] = []
        self._all_sections: list[SectionNode] = []
        self._lookup: dict[str, SectionNode] = {}

    def add_section(self, node: SectionNode) -> None:
        if node.parent:
            node.parent.children.append(node)
        else:
            self.root_sections.append(node)
        self._all_sections.append(node)
        self._lookup[node.section_number] = node

    def leaf_sections(self) -> list[SectionNode]:
        """Sections with no children — these contain the actual content."""
        return [s for s in self._all_sections if s.is_leaf]

    def all_sections(self) -> list[SectionNode]:
        return list(self._all_sections)

    def get(self, section_number: str) -> Optional[SectionNode]:
        return self._lookup.get(section_number)


# ── Base Extractor ───────────────────────────────────────────

class BaseStructureExtractor:
    """Base class for all structure extractors."""

    # Patterns that indicate a heading (used as fallback)
    HEADING_INDICATORS = re.compile(
        r'^(?:Chapter|Article|Section|PART|Rule)\s+',
        re.IGNORECASE
    )

    def extract(self, full_text: str, page_map: dict[int, int]) -> SectionTree:
        """
        Extract section structure from document text.

        Args:
            full_text: The complete document text.
            page_map: Mapping of character position → page number.

        Returns:
            A SectionTree representing the document hierarchy.
        """
        raise NotImplementedError


    @staticmethod
    def _split_lines(text: str, page_map: dict[int, int]) -> list[TextLine]:
        """Split text into lines with page number annotations.

        Uses character-position tracking as we iterate through lines,
        avoiding the O(n²) text.find() approach which breaks on duplicate
        lines by always returning the first occurrence.
        """
        lines = []
        sorted_page_map = sorted(page_map.items())  # [(char_pos, page_num), ...]

        char_pos = 0
        for i, raw_line in enumerate(text.split('\n')):
            line_text = raw_line.strip()
            if not line_text:
                char_pos += len(raw_line) + 1  # +1 for the \n delimiter
                continue

            # Find page for current character position in the accumulated text
            page = 1
            for pos, pg in sorted_page_map:
                if char_pos >= pos:
                    page = pg
                else:
                    break

            lines.append(TextLine(
                text=line_text,
                page_number=page,
                line_number=i + 1,
            ))
            char_pos += len(raw_line) + 1  # +1 for the \n delimiter

        return lines


# ── Legal Document Extractor ─────────────────────────────────

class LegalStructureExtractor(BaseStructureExtractor):
    """
    Extract structure from governing documents (General Laws, Bylaws, WOTM GL).

    Detects Moose-specific formatting:
      Part:       I. / V. / VII. / VIII.  (Roman numeral + period, standalone)
      Article:    ARTICLE I through ARTICLE XII (standalone line, title on next line)
      Section:    Sec. 24.5 - Jurisdiction  (or Section 24.5 - Title)
      Subsection: (a), (b), (c) at paragraph start
      Paragraph:  (1), (2), (3) at paragraph start

    Also handles generic legal patterns as fallback.
    """

    PATTERNS = [
        # Order matters: check most specific / highest-level first

        # Part: Roman numeral + period (standalone line, uppercase context)
        # Level 1 — top-level document divisions
        (SectionLevel.CHAPTER, re.compile(
            r'^([IVX]+)\.\s*$'
        )),

        # Part: "GENERAL LAWS" or "CONSTITUTION" — major division boundaries
        # Moose: the Constitution (Articles) and General Laws (Chapters) are
        # separate Parts; detecting the boundary prevents Chapters from being
        # incorrectly parented under the last Article (Art XII).
        (SectionLevel.CHAPTER, re.compile(
            r'^(GENERAL\s+LAWS|CONSTITUTION|THE\s+CONSTITUTION)\s*$'
        )),

        # Article: "ARTICLE IX" (standalone, title often on next line)
        # Level 2 — major divisions within Parts
        (SectionLevel.ARTICLE, re.compile(
            r'^ARTICLE\s+([IVXLCDM]+)\s*$'
        )),

        # Chapter: "Chapter 17 - Title" — groups of sections within Articles
        # Level 3 — between Article and Section
        (SectionLevel.SECTION, re.compile(
            r'^Chapter\s+(\d+)\s*[-—–]\s*(.+)$', re.IGNORECASE
        )),

        # Section: "Sec. 24.5 - Title" or "Section 24.5 - Title"
        # Level 4 — individual numbered provisions
        (SectionLevel.SUBSECTION, re.compile(
            r'^(?:Sec\.?|Section)\s+(\d+(?:\.\d+)*)\s*[-—–]\s*(.+)$',
            re.IGNORECASE
        )),

        # Subsection: "(a) Text..." at line start
        # Level 5 — lettered divisions within Sections
        (SectionLevel.PARAGRAPH, re.compile(
            r'^\(([a-z])\)\s+(.+)$'
        )),

        # Paragraph: "(1) Text..." at line start
        (SectionLevel.PARAGRAPH, re.compile(
            r'^\((\d+)\)\s+(.+)$'
        )),

        # Subparagraph: "(A) Text..." at line start
        (SectionLevel.SUBPARAGRAPH, re.compile(
            r'^\(([A-Z])\)\s+(.+)$'
        )),

        # Fallback: standalone numbered line like "24.3 Title"
        (SectionLevel.SECTION, re.compile(
            r'^(\d+(?:\.\d+)+)\s+([A-Z].+)$'
        )),
    ]

    # Article titles often appear on the line after "ARTICLE IX"
    ARTICLE_FOLLOW_PATTERN = re.compile(
        r'^([A-Z][A-Za-z\s/,&\-]{10,100})$'  # Title-looking line after ARTICLE marker
    )

    def extract(self, full_text: str, page_map: dict[int, int]) -> SectionTree:
        tree = SectionTree()
        stack: list[SectionNode] = []  # Ancestor stack during traversal
        sort_counter = 0
        pending_article_title: Optional[str] = None  # Moose: title on line after ARTICLE

        lines = self._split_lines(full_text, page_map)

        for i, line in enumerate(lines):
            # Moose pattern: ARTICLE IX (standalone) → next line is the title
            heading = self._detect_heading(line)

            if heading:
                # Pop stack to correct depth
                while stack and stack[-1].level >= heading.level:
                    stack.pop()

                parent = stack[-1] if stack else None

                # If this is an ARTICLE marker, check if next line is the title
                title = heading.title
                if heading.level == SectionLevel.ARTICLE.value and not title:
                    # Article marker like "ARTICLE IX" — look ahead for title
                    if i + 1 < len(lines):
                        next_line = lines[i + 1]
                        if self.ARTICLE_FOLLOW_PATTERN.match(next_line.text):
                            title = next_line.text
                            pending_article_title = title

                # Part headings (GENERAL LAWS, CONSTITUTION) use the heading
                # text as the title since they are standalone boundary markers
                if heading.level == SectionLevel.CHAPTER.value and not title:
                    # The heading number IS the title for Part-level markers
                    title = heading.number.strip().title()

                node = SectionNode(
                    section_number=heading.number,
                    title=title,
                    level=heading.level,
                    page_start=line.page_number,
                    page_end=line.page_number,
                    parent=parent,
                    sort_order=sort_counter,
                )
                sort_counter += 1
                tree.add_section(node)
                stack.append(node)

            # Skip ARTICLE title on next line (already consumed)
            elif pending_article_title and line.text == pending_article_title:
                pending_article_title = None
                if stack:
                    stack[-1].content_lines.append(line)
                    stack[-1].page_end = max(stack[-1].page_end, line.page_number)
                continue

            # Attach content to the deepest current section
            else:
                pending_article_title = None
                if stack:
                    stack[-1].content_lines.append(line)
                    stack[-1].page_end = max(stack[-1].page_end, line.page_number)

        # If no structure was detected, create a single flat section
        if not tree.root_sections:
            node = SectionNode(
                section_number="1",
                title="Full Document",
                level=1,
                page_start=1,
                page_end=max((line.page_number for line in lines), default=1),
                sort_order=0,
            )
            node.content_lines = lines
            tree.add_section(node)

        return tree

    def _detect_heading(self, line: TextLine) -> Optional[DetectedSection]:
        """Try to match the line against legal heading patterns."""
        if not line.text or len(line.text) > 200:
            return None

        for level, pattern in self.PATTERNS:
            match = pattern.match(line.text)
            if match:
                groups = match.groups()
                number = groups[0]
                title = groups[1] if len(groups) > 1 else ""

                # Build canonical section number
                if level == SectionLevel.SUBSECTION:
                    # "(a) Title" → need parent section number from stack
                    number = number.lower()
                elif level == SectionLevel.PARAGRAPH:
                    number = number
                elif level == SectionLevel.SUBPARAGRAPH:
                    number = number

                confidence = self._heading_confidence(line, level)
                if confidence > 0.3:
                    return DetectedSection(
                        level=level.value,
                        level_name=level.name.lower(),
                        number=number.strip(),
                        title=title.strip(),
                        page_number=line.page_number,
                        line_number=line.line_number,
                        confidence=confidence,
                    )

        return None

    @staticmethod
    def _heading_confidence(line: TextLine, level: SectionLevel) -> float:
        """Score how likely this line is a real heading.

        Base score from pattern specificity. Boosted by formatting cues when available.
        """
        # Base confidence by section level (more specific patterns = higher base)
        base_confidence = {
            SectionLevel.CHAPTER: 0.6,      # "I." or "Chapter X" is quite unambiguous
            SectionLevel.ARTICLE: 0.7,       # "ARTICLE IX" is very unambiguous
            SectionLevel.SECTION: 0.65,      # "Sec. 24.5 - Title" is very unambiguous
            SectionLevel.SUBSECTION: 0.5,    # "(a) Text" is moderately unambiguous
            SectionLevel.PARAGRAPH: 0.4,     # "(1) Text" could be ambiguous
            SectionLevel.SUBPARAGRAPH: 0.4,  # "(A) Text" could be ambiguous
        }.get(level, 0.5)

        score = base_confidence

        # Boost if formatting metadata is available
        if line.is_bold or line.font_size > 12:
            score = min(1.0, score + 0.3)
        if line.is_all_caps and level.value <= 3:
            score = min(1.0, score + 0.2)

        return score


# ── Handbook Extractor ───────────────────────────────────────

class HandbookStructureExtractor(BaseStructureExtractor):
    """
    Extract structure from officer handbooks and training guides.

    Detects:
      PART I: LODGE OFFICERS
      Governor — Duties and Responsibilities
      Junior Governor
      Financial Authority
    """

    PATTERNS = [
        (SectionLevel.CHAPTER, re.compile(
            r'^PART\s+(\d+|[IVXLCDM]+)[\s:.—]+(.+)$', re.IGNORECASE
        )),
        (SectionLevel.SECTION, re.compile(
            r'^(Governor|Jr\.?\s*Governor|Junior\s+Governor|Prelate|Treasurer|'
            r'Secretary|Trustee|Sergeant[-\s]at[-\s]Arms|Chaplain|Administrator|'
            r'President|Vice\s+President|Regent|Senior\s+Regent|Junior\s+Regent)'
            r'(?:\s*[—–-]\s*(.+))?$',
            re.IGNORECASE
        )),
        (SectionLevel.SUBSECTION, re.compile(
            r'^(Duties\s+and\s+Responsibilities?|Authority|Powers|Election|'
            r'Term\s+of\s+Office|Qualifications|Removal|Succession|'
            r'[A-Z][A-Za-z\s]{2,40})$'
        )),
    ]

    def extract(self, full_text: str, page_map: dict[int, int]) -> SectionTree:
        tree = SectionTree()
        stack: list[SectionNode] = []
        sort_counter = 0
        lines = self._split_lines(full_text, page_map)

        for line in lines:
            heading = self._detect_heading(line)

            if heading:
                while stack and stack[-1].level >= heading.level:
                    stack.pop()

                parent = stack[-1] if stack else None

                # For handbook, section number is the officer name / topic title
                section_num = heading.number.replace(" ", "_").lower()

                node = SectionNode(
                    section_number=section_num,
                    title=heading.title or heading.number,
                    level=heading.level,
                    page_start=line.page_number,
                    page_end=line.page_number,
                    parent=parent,
                    sort_order=sort_counter,
                )
                sort_counter += 1
                tree.add_section(node)
                stack.append(node)

            if stack:
                stack[-1].content_lines.append(line)
                stack[-1].page_end = max(stack[-1].page_end, line.page_number)

        if not tree.root_sections:
            node = SectionNode(
                section_number="1", title="Full Document", level=1,
                page_start=1, page_end=len(lines), sort_order=0,
            )
            node.content_lines = lines
            tree.add_section(node)

        return tree

    def _detect_heading(self, line: TextLine) -> Optional[DetectedSection]:
        for level, pattern in self.PATTERNS:
            match = pattern.match(line.text)
            if match:
                groups = match.groups()
                return DetectedSection(
                    level=level.value,
                    level_name=level.name.lower(),
                    number=groups[0].strip(),
                    title=groups[1].strip() if len(groups) > 1 and groups[1] else groups[0].strip(),
                    page_number=line.page_number,
                    line_number=line.line_number,
                    confidence=0.8,
                )
        return None


# ── Ritual Extractor ─────────────────────────────────────────

class RitualStructureExtractor(BaseStructureExtractor):
    """
    Extract structure from ritual and ceremonial documents.

    Detects:
      OPENING CEREMONY
      [Governor]: "I now declare this meeting open."
      [All]: (stand and face the altar)
    """

    PATTERNS = [
        (SectionLevel.CHAPTER, re.compile(
            r'^([A-Z][A-Z\s]+(?:CEREMONY|SERVICE|RITUAL|DEGREE|OBLIGATION))\s*$'
        )),
        (SectionLevel.SECTION, re.compile(
            r'^\[([A-Za-z\s/]+)\]:\s*(.*)$'
        )),
        (SectionLevel.SUBSECTION, re.compile(
            r'^(HYMN|SONG|PRAYER|PLEDGE)\b.*$', re.IGNORECASE
        )),
    ]

    def extract(self, full_text: str, page_map: dict[int, int]) -> SectionTree:
        tree = SectionTree()
        stack: list[SectionNode] = []
        sort_counter = 0
        lines = self._split_lines(full_text, page_map)

        for line in lines:
            heading = self._detect_heading(line)

            if heading:
                while stack and stack[-1].level >= heading.level:
                    stack.pop()

                parent = stack[-1] if stack else None
                node = SectionNode(
                    section_number=heading.number or str(sort_counter),
                    title=heading.title or heading.number,
                    level=heading.level,
                    page_start=line.page_number,
                    page_end=line.page_number,
                    parent=parent,
                    sort_order=sort_counter,
                )
                sort_counter += 1
                tree.add_section(node)
                stack.append(node)

            if stack:
                stack[-1].content_lines.append(line)
                stack[-1].page_end = max(stack[-1].page_end, line.page_number)

        if not tree.root_sections:
            node = SectionNode(
                section_number="1", title="Full Ritual", level=1,
                page_start=1, page_end=len(lines), sort_order=0,
            )
            node.content_lines = lines
            tree.add_section(node)

        return tree

    def _detect_heading(self, line: TextLine) -> Optional[DetectedSection]:
        for level, pattern in self.PATTERNS:
            match = pattern.match(line.text)
            if match:
                groups = match.groups()
                return DetectedSection(
                    level=level.value,
                    level_name=level.name.lower(),
                    number=groups[0].strip() if groups[0] else str(line.line_number),
                    title=groups[1].strip() if len(groups) > 1 and groups[1] else groups[0].strip(),
                    page_number=line.page_number,
                    line_number=line.line_number,
                    confidence=0.85,
                )
        return None


# ── Newsletter Extractor ─────────────────────────────────────

class NewsletterStructureExtractor(BaseStructureExtractor):
    """
    Extract articles from newsletters (Moose Leader).

    Detects articles by:
      - Large/bold headlines
      - Horizontal separators
      - Byline patterns: "By [Name]"
    """

    def extract(self, full_text: str, page_map: dict[int, int]) -> SectionTree:
        tree = SectionTree()
        lines = self._split_lines(full_text, page_map)

        # Simple heuristic: detect headlines as all-caps, short lines
        current_article = None
        article_count = 0

        for line in lines:
            # Heuristic: short, all-caps, or bold line → new article headline
            is_headline = (
                (line.is_all_caps and len(line.text) < 80) or
                (len(line.text) < 60 and line.text[0].isupper())
            )

            if is_headline and (not current_article or len(line.text) > 20):
                article_count += 1
                current_article = SectionNode(
                    section_number=str(article_count),
                    title=line.text,
                    level=2,
                    page_start=line.page_number,
                    page_end=line.page_number,
                    sort_order=article_count,
                )
                tree.add_section(current_article)

            if current_article:
                current_article.content_lines.append(line)
                current_article.page_end = max(
                    current_article.page_end, line.page_number
                )

        if not tree.root_sections:
            node = SectionNode(
                section_number="1", title="Full Newsletter", level=1,
                page_start=1, page_end=len(lines), sort_order=0,
            )
            node.content_lines = lines
            tree.add_section(node)

        return tree


# ── Factory ──────────────────────────────────────────────────

_EXTRACTORS = {
    "general_laws": LegalStructureExtractor,
    "constitution": LegalStructureExtractor,
    "wotm_general_laws": LegalStructureExtractor,
    "association_bylaws": LegalStructureExtractor,
    "local_bylaws": LegalStructureExtractor,
    "officer_handbook": HandbookStructureExtractor,
    "election_handbook": HandbookStructureExtractor,
    "social_quarters_rules": LegalStructureExtractor,  # Section-based
    "financial_policy": LegalStructureExtractor,
    "lodge_ritual": RitualStructureExtractor,
    "degree_ritual": RitualStructureExtractor,
    "memorial_service": RitualStructureExtractor,
    "installation_ceremony": RitualStructureExtractor,
    "newsletter": NewsletterStructureExtractor,
    "training_guide": HandbookStructureExtractor,
    "sports_rules": LegalStructureExtractor,  # Rule-numbered
    "activities_guidebook": HandbookStructureExtractor,
}


def get_structure_extractor(doc_type: str) -> BaseStructureExtractor:
    """Factory: return the appropriate structure extractor."""
    extractor_class = _EXTRACTORS.get(doc_type, LegalStructureExtractor)
    return extractor_class()
