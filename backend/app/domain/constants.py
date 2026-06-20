"""Domain tuning constants.

These are fixed algorithm parameters, intentionally *not*
env-driven — changing them changes retrieval behaviour and must be deliberate.
"""

from __future__ import annotations

# DocumentAnalyzer — word-count thresholds separating document types.
THESIS_MAX_WORDS = 2_000
ARTICLE_MAX_WORDS = 25_000
REVIEW_MAX_WORDS = 35_000

# DocumentSplitter — paragraph-aware packing target and overlap (in words).
SPLIT_TARGET_WORDS = 800
SPLIT_OVERLAP_WORDS = 150

# TextExtractor — quality score below this triggers a warning.
QUALITY_WARNING_THRESHOLD = 0.4

# MetadataExtractor — words fed to the LLM and max LLM attempts before fallback.
METADATA_CONTEXT_WORDS = 3_000
METADATA_MAX_ATTEMPTS = 3

# ChromaIndexer — sentence-transformers all-MiniLM-L6-v2 dimensionality.
EMBED_DIM = 384

# RAGPipeline — per-language retrieval fan-out (spec §5 step 3).
RETRIEVAL_TOP_K = 10
