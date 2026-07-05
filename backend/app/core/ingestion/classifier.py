"""
Document Classifier — Auto-classifies documents into the 13-tier Moose hierarchy.

Uses a combination of:
  1. Filename heuristics (fast, high-confidence signals)
  2. Content-based classification (keyword analysis)
  3. Admin override (always accepted)

In production, this would use a fine-tuned BERT model.
For MVP, we use keyword-based classification with high accuracy for Moose documents.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from app.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ClassificationResult:
    """Result of document classification."""
    doc_type: str               # e.g., "general_laws"
    tier: int                   # 1-13
    category: str               # governing, ritual, operational, etc.
    citation_format: str        # section, article, page, rule, module
    label: str                  # Human-readable: "General Laws"
    confidence: float           # 0.0 to 1.0
    needs_admin_review: bool    # True if confidence is low
    detected_jurisdiction: str  # international, state:XX, lodge:NNNN


# ── Document Type Definitions ────────────────────────────────

DOC_TYPES: dict[str, dict] = {
    "general_laws":           {"tier": 1,  "category": "governing",    "citation_format": "section", "label": "General Laws"},
    "constitution":           {"tier": 1,  "category": "governing",    "citation_format": "article", "label": "Constitution"},
    "lodge_ritual":           {"tier": 2,  "category": "ritual",       "citation_format": "page",    "label": "Lodge Ritual"},
    "degree_ritual":          {"tier": 2,  "category": "ritual",       "citation_format": "page",    "label": "Degree Ritual"},
    "memorial_service":       {"tier": 2,  "category": "ritual",       "citation_format": "page",    "label": "Memorial Service"},
    "installation_ceremony":  {"tier": 2,  "category": "ritual",       "citation_format": "page",    "label": "Installation Ceremony"},
    "officer_handbook":       {"tier": 3,  "category": "operational",  "citation_format": "section", "label": "Officer Handbook"},
    "election_handbook":      {"tier": 3,  "category": "operational",  "citation_format": "section", "label": "Election Handbook"},
    "social_quarters_rules":  {"tier": 3,  "category": "operational",  "citation_format": "section", "label": "Social Quarters Rules"},
    "financial_policy":       {"tier": 3,  "category": "operational",  "citation_format": "section", "label": "Financial Policy"},
    "meeting_procedure":      {"tier": 3,  "category": "operational",  "citation_format": "section", "label": "Meeting Procedure"},
    "membership_policy":      {"tier": 4,  "category": "membership",   "citation_format": "section", "label": "Membership Policy"},
    "discipline_policy":      {"tier": 4,  "category": "membership",   "citation_format": "section", "label": "Discipline Policy"},
    "code_of_conduct":        {"tier": 4,  "category": "membership",   "citation_format": "section", "label": "Code of Conduct"},
    "wotm_general_laws":      {"tier": 5,  "category": "wotm",         "citation_format": "article", "label": "WOTM General Laws"},
    "wotm_chapter_bylaws":    {"tier": 5,  "category": "wotm",         "citation_format": "article", "label": "WOTM Chapter Bylaws"},
    "wotm_ritual":            {"tier": 5,  "category": "wotm",         "citation_format": "page",    "label": "WOTM Ritual"},
    "legion_manual":          {"tier": 6,  "category": "legion",       "citation_format": "section", "label": "Moose Legion Manual"},
    "legion_ritual":          {"tier": 6,  "category": "legion",       "citation_format": "page",    "label": "Moose Legion Ritual"},
    "activities_guidebook":   {"tier": 7,  "category": "program",      "citation_format": "section", "label": "Activities Guidebook"},
    "activity_guidelines":    {"tier": 7,  "category": "program",      "citation_format": "section", "label": "Activity Guidelines"},
    "sports_rules":           {"tier": 7,  "category": "program",      "citation_format": "rule",    "label": "Sports Rules"},
    "youth_program":          {"tier": 7,  "category": "program",      "citation_format": "section", "label": "Youth Program"},
    "mooseheart_policy":      {"tier": 8,  "category": "charity",      "citation_format": "section", "label": "Mooseheart Policy"},
    "moosehaven_policy":      {"tier": 8,  "category": "charity",      "citation_format": "section", "label": "Moosehaven Policy"},
    "charities_policy":       {"tier": 8,  "category": "charity",      "citation_format": "section", "label": "Charities Policy"},
    "association_bylaws":     {"tier": 9,  "category": "association",  "citation_format": "article", "label": "Association Bylaws"},
    "local_bylaws":           {"tier": 10, "category": "local",        "citation_format": "article", "label": "Local Lodge Bylaws"},
    "house_rules":            {"tier": 10, "category": "local",        "citation_format": "section", "label": "House Rules"},
    "tax_compliance":         {"tier": 11, "category": "compliance",   "citation_format": "section", "label": "Tax Compliance"},
    "liquor_compliance":      {"tier": 11, "category": "compliance",   "citation_format": "section", "label": "Liquor Compliance"},
    "insurance_policy":       {"tier": 11, "category": "compliance",   "citation_format": "section", "label": "Insurance Policy"},
    "privacy_policy":         {"tier": 11, "category": "compliance",   "citation_format": "section", "label": "Privacy Policy"},
    "training_guide":         {"tier": 12, "category": "training",     "citation_format": "module",  "label": "Training Guide"},
    "newsletter":             {"tier": 12, "category": "training",     "citation_format": "article", "label": "Newsletter"},
    "convention_proceedings": {"tier": 12, "category": "training",     "citation_format": "page",    "label": "Convention Proceedings"},
    "form_template":          {"tier": 13, "category": "form",         "citation_format": "form",    "label": "Form / Template"},
    "other":                  {"tier": 12, "category": "other",        "citation_format": "section", "label": "Other Document"},
}


# ── Filename Heuristics ──────────────────────────────────────

FILENAME_PATTERNS: dict[str, list[str]] = {
    "general_laws":          [r"general[_\s-]?laws?", r"\bGL\b", r"governing[_\s-]?document"],
    "wotm_general_laws":     [r"wotm[_\s-]?general[_\s-]?laws?", r"women[_\s-]of[_\s-]the[_\s-]moose"],
    "officer_handbook":      [r"officer[_\s-]?(?:and[_\s-]?)?committeemen[_\s-]?handbook", r"officer[_\s-]?handbook"],
    "election_handbook":     [r"election[_\s-]?handbook", r"election[_\s-]?guide"],
    "social_quarters_rules": [r"social[_\s-]?quarters?", r"\bbar\b[_\s-]?rules?", r"sq[_\s-]?rules"],
    "lodge_ritual":          [r"lodge[_\s-]?ritual", r"ritual[_\s-]?handbook"],
    "legion_manual":         [r"legion[_\s-]?manual", r"moose[_\s-]?legion"],
    "newsletter":            [r"moose[_\s-]?leader", r"newsletter", r"bulletin"],
    "sports_rules":          [r"bowling", r"darts?\b", r"golf", r"pool[_\s-]?rules?", r"horseshoes"],
    "activity_guidelines":   [r"activity[_\s-]?group", r"guide[_\s-]?lines"],
    "financial_policy":      [r"financ", r"credit[_\s-]?card", r"budget", r"purchas"],
    "local_bylaws":          [r"lodge[_\s-]?bylaws?", r"local[_\s-]?bylaws?"],
    "association_bylaws":    [r"association[_\s-]?bylaws?", r"state[_\s-]?bylaws?"],
}


# ── Content Keyword Patterns ─────────────────────────────────

CONTENT_KEYWORDS: dict[str, list[str]] = {
    "general_laws":          [r"\bgeneral\s+laws?\b", r"constitution\s+and\s+general\s+laws", r"governing\s+document", r"supreme\s+laws?"],
    "lodge_ritual":          [r"9\s+o['\u2019]clock\s+ceremony", r"\bobligation\b", r"\binitiation\b", r"\baltar\b"],
    "officer_handbook":      [r"duties\s+and\s+responsibilities", r"governor\s+shall", r"authority\s+of\s+the"],
    "social_quarters_rules": [r"social\s+quarters?", r"\bbartender\b", r"\bliquor\b", r"\bbar\s+operations?\b"],
    "election_handbook":     [r"\bnomination\b", r"\bballot\b", r"\belection\s+of\s+officers"],
    "financial_policy":      [r"\bbudget\b", r"\baudit\b", r"\bexpenditure\b", r"\btax\b"],
    "discipline_policy":     [r"\bsuspension\b", r"\bexpulsion\b", r"\bcharges?\b", r"\bhearing\b"],
    "newsletter":            [r"\bvolume\b.*\bissue\b", r"\bnewsletter\b", r"\bmoose\s+leader\b"],
}


class DocumentClassifier:
    """Classify Moose documents into the 13-tier hierarchy."""

    def classify(
        self, preview_text: str, filename: str = ""
    ) -> ClassificationResult:
        """
        Classify a document based on filename heuristics and content analysis.

        Args:
            preview_text: First few pages of document text.
            filename: Original filename (for heuristic matching).

        Returns:
            ClassificationResult with doc_type, tier, category, citation_format.
        """
        # 1. Filename heuristics (fast, high-confidence)
        filename_result = self._classify_by_filename(filename)

        # 2. Content analysis
        content_result = self._classify_by_content(preview_text)

        # 3. Merge results
        if filename_result and content_result:
            if filename_result[0] == content_result[0]:
                # Both agree → high confidence
                doc_type = filename_result[0]
                confidence = max(filename_result[1], content_result[1])
            else:
                # Disagreement → prefer content, lower confidence
                doc_type = content_result[0]
                confidence = content_result[1] * 0.7
        elif filename_result:
            doc_type, confidence = filename_result
        elif content_result:
            doc_type, confidence = content_result
        else:
            doc_type = "other"
            confidence = 0.3

        # 4. Get type metadata
        type_info = DOC_TYPES.get(doc_type, DOC_TYPES["other"])

        # 5. Detect jurisdiction from filename/content
        jurisdiction = self._detect_jurisdiction(filename, preview_text)

        return ClassificationResult(
            doc_type=doc_type,
            tier=type_info["tier"],
            category=type_info["category"],
            citation_format=type_info["citation_format"],
            label=type_info["label"],
            confidence=round(confidence, 2),
            needs_admin_review=(confidence < 0.80),
            detected_jurisdiction=jurisdiction,
        )

    def _classify_by_filename(self, filename: str) -> Optional[tuple[str, float]]:
        """Classify using filename patterns. Returns (doc_type, confidence) or None."""
        if not filename:
            return None

        name_lower = Path(filename).stem.lower().replace("_", " ").replace("-", " ")

        for doc_type, patterns in FILENAME_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, name_lower, re.IGNORECASE):
                    return (doc_type, 0.90)  # Filename matches are strong signals

        return None

    def _classify_by_content(self, text: str) -> Optional[tuple[str, float]]:
        """Classify using keyword analysis of document content."""
        if not text or len(text) < 100:
            return None

        text_lower = text.lower()
        best_type = None
        best_score = 0.0

        for doc_type, patterns in CONTENT_KEYWORDS.items():
            score = 0.0
            matches = 0
            for pattern in patterns:
                if re.search(pattern, text_lower):
                    matches += 1
            if matches > 0:
                score = min(0.9, 0.5 + (matches * 0.15))

            if score > best_score:
                best_score = score
                best_type = doc_type

        if best_type and best_score > 0.4:
            return (best_type, best_score)

        return None

    def _detect_jurisdiction(self, filename: str, text: str) -> str:
        """Detect jurisdiction scope: international, state:XX, or lodge:NNNN."""
        combined = (filename + " " + text[:500]).lower()

        # State patterns
        state_patterns = {
            "state:IL": [r"\billinois\b", r"\bIL\b"],
            "state:FL": [r"\bflorida\b", r"\bFL\b"],
            "state:CA": [r"\bcalifornia\b", r"\bCA\b"],
            "state:TX": [r"\btexas\b", r"\bTX\b"],
            "state:NY": [r"\bnew york\b", r"\bNY\b"],
            "state:PA": [r"\bpennsylvania\b", r"\bPA\b"],
            "state:OH": [r"\bohio\b", r"\bOH\b"],
            "province:ON": [r"\bontario\b", r"\bON\b"],
            "province:BC": [r"\bbritish columbia\b", r"\bBC\b"],
        }

        for jurisdiction, patterns in state_patterns.items():
            if any(re.search(p, combined, re.IGNORECASE) for p in patterns):
                return jurisdiction

        # Lodge number pattern: "Lodge #1234" or "Lodge 1234"
        lodge_match = re.search(r'lodge\s*#?\s*(\d{3,5})', combined, re.IGNORECASE)
        if lodge_match:
            return f"lodge:{lodge_match.group(1)}"

        # Association pattern
        if re.search(r'association\s+(?:of|bylaws)', combined, re.IGNORECASE):
            return "association"

        return "international"
