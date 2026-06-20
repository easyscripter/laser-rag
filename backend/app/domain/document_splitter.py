"""DocumentSplitter — paragraph-aware chunking (spec §4 stage 4).

Packs whole paragraphs greedily toward ``SPLIT_TARGET_WORDS`` and carries a
``SPLIT_OVERLAP_WORDS`` tail of words into the next chunk so context spans
boundaries. Paragraphs longer than the target become their own chunk rather
than being split mid-sentence.
"""

from __future__ import annotations

import re

from app.domain.constants import SPLIT_OVERLAP_WORDS, SPLIT_TARGET_WORDS
from app.domain.models import Chunk

# Paragraphs are separated by one or more blank lines (see TextExtractor normalize).
_PARAGRAPH_RE = re.compile(r"\n\s*\n")
_WORD_RE = re.compile(r"\S+")


class DocumentSplitter:
    """Splits normalized text into overlapping, paragraph-aligned chunks."""

    def __init__(
        self,
        target_words: int = SPLIT_TARGET_WORDS,
        overlap_words: int = SPLIT_OVERLAP_WORDS,
    ) -> None:
        if overlap_words >= target_words:
            raise ValueError("overlap_words must be smaller than target_words")
        self._target = target_words
        self._overlap = overlap_words

    def split(self, text: str) -> list[Chunk]:
        """Return ordered chunks covering ``text`` with overlap."""
        paragraphs = [p.strip() for p in _PARAGRAPH_RE.split(text) if p.strip()]
        if not paragraphs:
            return []

        chunks: list[Chunk] = []
        current: list[str] = []  # words buffered for the chunk being built
        index = 0

        for paragraph in paragraphs:
            words = _WORD_RE.findall(paragraph)
            if current and len(current) + len(words) > self._target:
                chunks.append(self._make_chunk(index, current))
                index += 1
                current = current[-self._overlap :]  # carry overlap into next chunk
            current.extend(words)

        if current:
            chunks.append(self._make_chunk(index, current))
        return chunks

    def _make_chunk(self, index: int, words: list[str]) -> Chunk:
        return Chunk(index=index, text=" ".join(words), n_words=len(words))
