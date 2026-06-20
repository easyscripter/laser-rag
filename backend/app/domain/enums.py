"""Domain enumerations (spec §3.1)."""

from __future__ import annotations

from enum import StrEnum


class DocumentType(StrEnum):
    """Document class inferred from word count (DocumentAnalyzer)."""

    THESIS = "thesis"  # < 2k words
    ARTICLE = "article"  # 2k-25k words
    REVIEW = "review"  # 25k-35k words
    MONOGRAPH = "monograph"  # > 35k words


class Language(StrEnum):
    """Dominant language detected by character composition (Cyrillic vs Latin)."""

    RU = "ru"
    EN = "en"
