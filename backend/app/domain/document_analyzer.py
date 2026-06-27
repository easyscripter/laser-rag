"""DocumentAnalyzer — infer document type and language (spec §4 stage 2).

Type follows word-count thresholds from the article; language is decided by the
ratio of Cyrillic vs Latin letters. Both feed the splitter and search priority.
"""

from __future__ import annotations

import re

from app.domain.constants import (
    ARTICLE_MAX_WORDS,
    REVIEW_MAX_WORDS,
    THESIS_MAX_WORDS,
)
from app.domain.enums import DocumentType
from app.domain.language import detect_language
from app.domain.models import AnalysisResult

_WORD_RE = re.compile(r"\S+")


class DocumentAnalyzer:
    """Classifies a document by length and dominant language."""

    def analyze(self, text: str) -> AnalysisResult:
        """Return the inferred type and language for ``text``."""
        n_words = len(_WORD_RE.findall(text))
        return AnalysisResult(
            doc_type=self._classify_type(n_words),
            lang=detect_language(text),
            n_words=n_words,
        )

    def _classify_type(self, n_words: int) -> DocumentType:
        if n_words < THESIS_MAX_WORDS:
            return DocumentType.THESIS
        if n_words < ARTICLE_MAX_WORDS:
            return DocumentType.ARTICLE
        if n_words < REVIEW_MAX_WORDS:
            return DocumentType.REVIEW
        return DocumentType.MONOGRAPH
