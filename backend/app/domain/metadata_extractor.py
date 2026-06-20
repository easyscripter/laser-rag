"""MetadataExtractor — bibliographic metadata via LLM (spec §4 stage 3).

Feeds the first ``METADATA_CONTEXT_WORDS`` words to the injected ``LLMClient``,
parses the JSON reply into ``DocumentMetadata`` and retries up to
``METADATA_MAX_ATTEMPTS``. If the model never returns valid JSON, it falls back
to a title derived from the filename so indexing can still proceed (spec §4:
"fallback ≤3, иначе по имени файла").

Model tier is chosen by document type — fast model for articles, long-context
for monographs — expressed through the opaque ``task`` label the LLM layer reads.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from app.domain.constants import METADATA_CONTEXT_WORDS, METADATA_MAX_ATTEMPTS
from app.domain.enums import DocumentType
from app.domain.models import DocumentMetadata
from app.domain.protocols import LLMClient
from app.prompts.metadata import METADATA_EXTRACTION_PROMPT

_WORD_RE = re.compile(r"\S+")
# Models often wrap JSON in ```json … ``` fences; strip them before parsing.
_JSON_FENCE_RE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.IGNORECASE)


class MetadataExtractor:
    """Extracts structured bibliographic metadata using an injected LLM."""

    def __init__(self, llm: LLMClient) -> None:
        self._llm = llm

    async def extract(
        self,
        text: str,
        *,
        doc_type: DocumentType,
        filename: str,
    ) -> DocumentMetadata:
        """Return metadata for ``text``; fall back to the filename on failure."""
        excerpt = self._head(text, METADATA_CONTEXT_WORDS)
        prompt = METADATA_EXTRACTION_PROMPT.format(excerpt=excerpt)
        task = self._task_for(doc_type)

        for _attempt in range(METADATA_MAX_ATTEMPTS):
            try:
                raw = await self._llm.complete(prompt, task=task)
                return self._parse(raw)
            except (json.JSONDecodeError, ValueError):
                continue  # malformed reply — retry until attempts exhausted

        return self._fallback(filename)

    def _head(self, text: str, n_words: int) -> str:
        return " ".join(_WORD_RE.findall(text)[:n_words])

    def _task_for(self, doc_type: DocumentType) -> str:
        # Monographs/reviews are long → long-context model; the rest → fast model.
        if doc_type in (DocumentType.MONOGRAPH, DocumentType.REVIEW):
            return "metadata_long"
        return "metadata_fast"

    def _parse(self, raw: str) -> DocumentMetadata:
        cleaned = _JSON_FENCE_RE.sub("", raw.strip())
        data = json.loads(cleaned)
        if not isinstance(data, dict):
            raise ValueError("LLM metadata is not a JSON object")
        return DocumentMetadata.model_validate(data)

    def _fallback(self, filename: str) -> DocumentMetadata:
        """Last resort: derive a human title from the file stem."""
        stem = Path(filename).stem.replace("_", " ").replace("-", " ").strip()
        return DocumentMetadata(title=stem or filename)
