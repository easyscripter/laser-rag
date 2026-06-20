"""TextExtractor — raw file → normalized text + quality score (spec §4 stage 1).

Supports PDF (pypdf), DOCX (python-docx), ODT (odfpy), TXT and MD. Computes a
SHA-256 over the *raw bytes* (dedup key, spec §8) and a 0.0-1.0 quality score
heuristic; scores below ``QUALITY_WARNING_THRESHOLD`` attach a warning.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from app.domain.constants import QUALITY_WARNING_THRESHOLD
from app.domain.models import ExtractionResult
from app.errors.domain import UnsupportedFormatError

_WORD_RE = re.compile(r"\S+")
# Collapse runs of blank lines so paragraph boundaries stay meaningful downstream.
_MULTI_BLANK_RE = re.compile(r"\n{3,}")
_REPLACEMENT_CHAR = "�"

SUPPORTED_EXTENSIONS = frozenset({".pdf", ".docx", ".odt", ".txt", ".md"})


class TextExtractor:
    """Extracts normalized text from a document file."""

    def extract(self, path: str | Path) -> ExtractionResult:
        """Read ``path`` and return extracted text with quality metadata."""
        file_path = Path(path)
        suffix = file_path.suffix.lower()
        if suffix not in SUPPORTED_EXTENSIONS:
            raise UnsupportedFormatError(f"unsupported extension: {suffix!r}")

        raw = file_path.read_bytes()
        sha256 = hashlib.sha256(raw).hexdigest()

        text, n_pages = self._dispatch(file_path, suffix, raw)
        text = self._normalize(text)

        n_words = len(_WORD_RE.findall(text))
        quality_score = self._quality_score(text)
        warning = (
            f"low extraction quality ({quality_score:.2f})"
            if quality_score < QUALITY_WARNING_THRESHOLD
            else None
        )

        return ExtractionResult(
            text=text,
            sha256=sha256,
            quality_score=quality_score,
            n_pages=n_pages,
            n_words=n_words,
            warning=warning,
        )

    def _dispatch(self, path: Path, suffix: str, raw: bytes) -> tuple[str, int]:
        """Return (text, n_pages); n_pages is 0 when the format has no page concept."""
        match suffix:
            case ".pdf":
                return self._extract_pdf(path)
            case ".docx":
                return self._extract_docx(path), 0
            case ".odt":
                return self._extract_odt(path), 0
            case ".txt" | ".md":
                return raw.decode("utf-8", errors="replace"), 0
            case _:  # defensive — already guarded by SUPPORTED_EXTENSIONS
                raise UnsupportedFormatError(f"unsupported extension: {suffix!r}")

    def _extract_pdf(self, path: Path) -> tuple[str, int]:
        from pypdf import PdfReader

        reader = PdfReader(str(path))
        pages = [page.extract_text() or "" for page in reader.pages]
        return "\n\n".join(pages), len(pages)

    def _extract_docx(self, path: Path) -> str:
        from docx import Document

        document = Document(str(path))
        return "\n\n".join(p.text for p in document.paragraphs)

    def _extract_odt(self, path: Path) -> str:
        from odf import teletype, text
        from odf.opendocument import load

        document = load(str(path))
        paragraphs = document.getElementsByType(text.P)
        return "\n\n".join(teletype.extractText(p) for p in paragraphs)

    def _normalize(self, text: str) -> str:
        """Trim, unify newlines, and collapse excessive blank lines."""
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        text = _MULTI_BLANK_RE.sub("\n\n", text)
        return text.strip()

    def _quality_score(self, text: str) -> float:
        """Fraction of printable characters, penalized by replacement chars.

        Garbled extractions (scanned PDFs, broken encodings) surface as runs of
        ``\\ufffd`` or control bytes and score low; clean text scores near 1.0.
        """
        total = len(text)
        if total == 0:
            return 0.0
        printable = sum(1 for c in text if c.isprintable() or c in "\n\t")
        replacements = text.count(_REPLACEMENT_CHAR)
        score = (printable - replacements) / total
        return max(0.0, min(1.0, score))
