"""Utilities for interacting with PDF files."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from PyPDF2 import PdfReader
from pdfminer.high_level import extract_text


def pdf_page_count(path: Path) -> int:
    """Return the number of pages in the provided PDF file."""

    with path.open("rb") as handle:
        reader = PdfReader(handle)
        return len(reader.pages)


def pdf_extract_text(path: Path, max_pages: int = 3) -> str:
    """Extract a limited amount of text from the PDF."""

    if max_pages <= 0:
        return ""
    try:
        text = extract_text(str(path), maxpages=max_pages)
        if text and text.strip():
            return text
    except Exception:  # pragma: no cover - pdfminer failures surface as warnings
        text = ""
    # Fallback: read raw bytes (useful for synthetic PDFs where extractors return empty)
    try:
        with path.open("rb") as fh:
            raw = fh.read(200_000)  # limit to 200KB
        return text + "\n" + raw.decode("latin-1", errors="ignore")
    except Exception:
        return text or ""


def contains_keywords(text: str, keywords: Iterable[str]) -> bool:
    """Check if all keywords are present in the text."""

    lowered = text.lower()
    return all(keyword.lower() in lowered for keyword in keywords)


def contains_forbidden(text: str, keywords: Iterable[str]) -> bool:
    """Check if any forbidden keyword exists in the text."""

    lowered = text.lower()
    return any(keyword.lower() in lowered for keyword in keywords)


__all__ = [
    "pdf_page_count",
    "pdf_extract_text",
    "contains_keywords",
    "contains_forbidden",
]
