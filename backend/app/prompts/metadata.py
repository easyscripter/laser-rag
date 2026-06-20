"""Prompt template for bibliographic metadata extraction (spec §4 stage 3)."""

from __future__ import annotations

METADATA_EXTRACTION_PROMPT = (
    "Extract bibliographic metadata from the document excerpt below and return "
    "ONLY a JSON object with keys: title, authors (array of strings), abstract, "
    "keywords (array of strings), doi, url, year (integer), journal. Use null for "
    "unknown fields.\n\n--- DOCUMENT ---\n{excerpt}\n--- END ---"
)
