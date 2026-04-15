"""
PDF Text Extraction Module

Attempts multiple extraction strategies in order of robustness:
1. pymupdf (fitz) - Most robust, best text extraction for text-based PDFs
2. OCR via easyocr - Fallback for scanned/image-only PDFs
"""
import os
import logging
from typing import Optional, Tuple

from backend.config import PDF_OCR_ENABLED, PDF_OCR_LANGUAGES

logger = logging.getLogger(__name__)


class PDFExtractor:
    """Multi-strategy PDF text extraction with OCR fallback."""

    def __init__(self, ocr_languages: list = None):
        self.ocr_languages = ocr_languages or PDF_OCR_LANGUAGES
        self._easyocr_initialized = False
        self._ocr_reader = None

    def initialize_ocr(self):
        """Lazy initialization of easyocr reader."""
        if not self._easyocr_initialized:
            import easyocr
            self._ocr_reader = easyocr.Reader(self.ocr_languages, gpu=False)
            self._easyocr_initialized = True

    def extract_with_pymupdf(self, file_path: str) -> Optional[str]:
        """Extract text using pymupdf (fitz) - most robust method."""
        try:
            import fitz  # pymupdf
            doc = fitz.open(file_path)
            text_parts = []
            for page in doc:
                page_text = page.get_text()
                if page_text:
                    text_parts.append(page_text.strip())
            doc.close()
            if text_parts:
                return '\n\n'.join(text_parts)
        except Exception as e:
            logger.debug(f"pymupdf extraction failed: {e}")
        return None

    def extract_with_ocr(self, file_path: str) -> Optional[str]:
        """Extract text using OCR (easyocr) for scanned/image PDFs."""
        try:
            self.initialize_ocr()
            import fitz  # pymupdf for PDF-to-image conversion

            # Convert PDF pages to images at 150 DPI for better OCR accuracy
            doc = fitz.open(file_path)
            all_text = []

            for page_num in range(len(doc)):
                page = doc[page_num]
                mat = fitz.Matrix(150, 150)  # Higher DPI for better OCR
                pm = page.get_pixmap(matrix=mat)

                img_data = pm.tobytes("png")
                result = self._ocr_reader.readtext(img_data)
                page_text = " ".join([r[1] for r in result])
                if page_text.strip():
                    all_text.append(f"[Page {page_num + 1}]\n{page_text.strip()}")

            doc.close()

            if all_text:
                return '\n\n'.join(all_text)

        except Exception as e:
            logger.error(f"OCR extraction failed: {e}")
        return None

    def extract(self, file_path: str, use_ocr: bool = None) -> Tuple[Optional[str], str]:
        """
        Extract text from PDF using multiple strategies.

        Args:
            file_path: Path to the PDF file
            use_ocr: Whether to use OCR fallback. If None, uses config.PDF_OCR_ENABLED

        Returns:
            Tuple of (extracted_text, strategy_used)
        """
        if use_ocr is None:
            use_ocr = PDF_OCR_ENABLED

        # Order: pymupdf (most robust) -> OCR (fallback)
        strategies = [
            (self.extract_with_pymupdf, "pymupdf"),
        ]

        if use_ocr:
            strategies.append((self.extract_with_ocr, "easyocr"))

        for strategy, name in strategies:
            text = strategy(file_path)
            if text and len(text.strip()) > 50:  # Minimum content threshold
                logger.info(f"PDF text extraction successful using {name}")
                return text, name

        return None, "none"
