"""Language detection by character composition (spec §4 stage 2, §5 step 1).

Shared by ``DocumentAnalyzer`` (classify a document) and the chat engine (detect
the query language before cross-lingual retrieval), so the heuristic lives in one
place rather than being duplicated.
"""

from __future__ import annotations

import re

from app.domain.enums import Language

_CYRILLIC_RE = re.compile(r"[Ѐ-ӿ]")
_LATIN_RE = re.compile(r"[A-Za-z]")

# Human-readable names for translation prompts (spec §5 step 2).
LANGUAGE_NAMES: dict[Language, str] = {
    Language.RU: "Russian",
    Language.EN: "English",
}


def detect_language(text: str) -> Language:
    """Cyrillic-dominant → ru, otherwise en (Latin is the default script)."""
    cyrillic = len(_CYRILLIC_RE.findall(text))
    latin = len(_LATIN_RE.findall(text))
    return Language.RU if cyrillic > latin else Language.EN


def other_language(lang: Language) -> Language:
    """The complementary language to search/translate into (spec §5 step 2)."""
    return Language.EN if lang is Language.RU else Language.RU
