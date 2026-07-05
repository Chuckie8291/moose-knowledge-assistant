"""
OCR Engine — Abstract interface with Tesseract and Textract implementations.

Tiered approach:
  1. Digital text → No OCR needed
  2. Clean scan → Tesseract 5 (local, free)
  3. Poor quality / handwriting → AWS Textract (cloud, high-accuracy)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

from app.config import settings
from app.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class OCRResult:
    """Result of OCR processing a single page."""
    page_number: int
    text: str
    confidence: float              # 0.0 to 1.0
    engine: str                    # "tesseract_5" | "textract" | "none"
    word_confidences: list[dict] = field(default_factory=list)
    # [{"word": "The", "confidence": 0.99, "bbox": [x, y, w, h]}, ...]
    low_confidence_words: list[dict] = field(default_factory=list)


@dataclass
class OCRDecision:
    """Decision about whether and how to OCR a document."""
    needs_ocr: bool
    engine: str                    # "none" | "tesseract" | "textract" | "mixed"
    reason: str
    scanned_page_indices: list[int] = field(default_factory=list)
    # For mixed PDFs: which pages to OCR


class BaseOCREngine(ABC):
    """Abstract OCR engine."""

    @abstractmethod
    def process_page(self, image_bytes: bytes, page_number: int) -> OCRResult:
        """OCR a single page image."""
        ...

    @abstractmethod
    def process_document(self, image_bytes_list: list[bytes]) -> list[OCRResult]:
        """OCR a multi-page document (e.g., TIFF, scanned PDF)."""
        ...


class NoOCREngine(BaseOCREngine):
    """Used when text is already extractable — no OCR needed."""

    def process_page(self, image_bytes: bytes, page_number: int) -> OCRResult:
        return OCRResult(
            page_number=page_number,
            text="",
            confidence=1.0,
            engine="none",
        )

    def process_document(self, image_bytes_list: list[bytes]) -> list[OCRResult]:
        return [
            OCRResult(page_number=i + 1, text="", confidence=1.0, engine="none")
            for i in range(len(image_bytes_list))
        ]


class TesseractOCREngine(BaseOCREngine):
    """Local OCR using Tesseract 5 with image preprocessing."""

    def process_page(self, image_bytes: bytes, page_number: int) -> OCRResult:
        try:
            import pytesseract
            from PIL import Image
            import cv2
            import numpy as np
        except ImportError:
            logger.warning("Tesseract dependencies not installed; returning empty result")
            return OCRResult(page_number=page_number, text="", confidence=0.0, engine="tesseract_5")

        # Load image
        pil_image = Image.open(io.BytesIO(image_bytes))
        cv_image = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)

        # Preprocessing pipeline
        gray = cv2.cvtColor(cv_image, cv2.COLOR_BGR2GRAY)
        denoised = cv2.fastNlMeansDenoising(gray, h=30)
        binary = cv2.adaptiveThreshold(
            denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY, 31, 2
        )

        # OCR
        config = settings.ocr_tesseract_config
        text = pytesseract.image_to_string(binary, config=config)

        # Per-word confidence
        data = pytesseract.image_to_data(
            binary, config=config, output_type=pytesseract.Output.DICT
        )
        word_confidences = []
        low_confidence_words = []
        confidences = []

        for i in range(len(data["text"])):
            word = data["text"][i].strip()
            if not word:
                continue
            conf = int(data["conf"][i]) / 100.0
            confidences.append(conf)
            word_info = {
                "word": word,
                "confidence": conf,
                "bbox": [
                    data["left"][i], data["top"][i],
                    data["width"][i], data["height"][i]
                ],
            }
            word_confidences.append(word_info)
            if conf < settings.ocr_min_confidence:
                low_confidence_words.append(word_info)

        avg_confidence = sum(confidences) / max(len(confidences), 1)

        return OCRResult(
            page_number=page_number,
            text=self._clean_text(text),
            confidence=avg_confidence,
            engine="tesseract_5",
            word_confidences=word_confidences,
            low_confidence_words=low_confidence_words,
        )

    def process_document(self, image_bytes_list: list[bytes]) -> list[OCRResult]:
        return [
            self.process_page(img, i + 1)
            for i, img in enumerate(image_bytes_list)
        ]

    @staticmethod
    def _clean_text(text: str) -> str:
        """Clean common OCR artifacts."""
        import re
        text = re.sub(r'§\s+', '§', text)          # Fix section symbol spacing
        text = re.sub(r'(\d)\.(\d)', r'\1.\2', text)  # Fix broken decimals
        text = re.sub(r'\n{3,}', '\n\n', text)       # Collapse excessive newlines
        return text.strip()


class TextractOCREngine(BaseOCREngine):
    """
    AWS Textract OCR — high accuracy for poor-quality scans.
    Requires AWS credentials configured.

    NOTE: This is a stub. Full implementation requires:
      - boto3 textract client
      - Async job submission + polling for multi-page docs
      - S3 upload of images (Textract requires S3 for async jobs)
    """

    def process_page(self, image_bytes: bytes, page_number: int) -> OCRResult:
        logger.warning("Textract engine not fully implemented — returning empty result")
        return OCRResult(
            page_number=page_number,
            text="",
            confidence=0.0,
            engine="textract",
        )

    def process_document(self, image_bytes_list: list[bytes]) -> list[OCRResult]:
        return [
            OCRResult(page_number=i + 1, text="", confidence=0.0, engine="textract")
            for i in range(len(image_bytes_list))
        ]


# ── Factory ──────────────────────────────────────────────────

def get_ocr_engine(engine_name: str) -> BaseOCREngine:
    """Factory: return the appropriate OCR engine."""
    engines = {
        "none": NoOCREngine(),
        "tesseract": TesseractOCREngine(),
        "textract": TextractOCREngine(),
    }
    return engines.get(engine_name, NoOCREngine())


class OCRDecisionEngine:
    """Decides which OCR engine to use based on document analysis."""

    MIN_CHARS_PER_PAGE = 50

    def decide(self, loaded_doc: "LoadedDocument") -> OCRDecision:
        """Analyze loaded document and determine OCR strategy."""

        # Already digital
        if loaded_doc.is_digital:
            return OCRDecision(
                needs_ocr=False,
                engine="none",
                reason="Digital document with extractable text",
            )

        # Image — always needs OCR
        if loaded_doc.file_ext in ('.png', '.jpg', '.jpeg', '.tiff', '.tif'):
            return OCRDecision(
                needs_ocr=True,
                engine=settings.ocr_default_engine,
                reason=f"Image file ({loaded_doc.file_ext}) requires OCR",
                scanned_page_indices=list(range(len(loaded_doc.pages))),
            )

        # PDF — check per-page
        text_ratio = sum(
            1 for p in loaded_doc.pages if p.char_count >= self.MIN_CHARS_PER_PAGE
        ) / max(len(loaded_doc.pages), 1)

        if text_ratio >= 0.90:
            return OCRDecision(needs_ocr=False, engine="none",
                              reason=f"Digital PDF: {text_ratio:.0%} pages with text")
        elif text_ratio >= 0.30:
            scanned = [
                i for i, p in enumerate(loaded_doc.pages)
                if p.char_count < self.MIN_CHARS_PER_PAGE
            ]
            return OCRDecision(
                needs_ocr=True, engine="mixed",
                reason=f"Mixed PDF: {text_ratio:.0%} pages digital, {len(scanned)} need OCR",
                scanned_page_indices=scanned,
            )
        else:
            return OCRDecision(
                needs_ocr=True,
                engine=settings.ocr_default_engine,
                reason=f"Scanned PDF: only {text_ratio:.0%} pages with text",
                scanned_page_indices=list(range(len(loaded_doc.pages))),
            )
