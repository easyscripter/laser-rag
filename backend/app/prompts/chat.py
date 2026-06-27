"""Prompt templates for the conversational RAG flow (spec §5)."""

from __future__ import annotations

# Step 0 — rewrite a follow-up into a standalone query using the history.
CONDENSE_PROMPT = (
    "Given the conversation history and a follow-up question, rewrite the follow-up "
    "as a standalone question in its original language. Preserve all entities and "
    "intent. Return ONLY the rewritten question, with no preamble.\n\n"
    "--- HISTORY ---\n{history}\n--- FOLLOW-UP ---\n{question}\n"
    "--- STANDALONE QUESTION ---"
)

# Step 2 — translate the query into the other language for cross-lingual search.
TRANSLATE_PROMPT = (
    "Translate the following search query into {target_language}. Return ONLY the "
    "translation, with no quotes or explanations.\n\n{query}"
)

# History overflow — summarize older turns into one compact paragraph.
SUMMARY_PROMPT = (
    "Summarize the following conversation excerpt into a concise paragraph that "
    "preserves facts, entities and intent. Return ONLY the summary.\n\n{history}"
)

# Step 5 — grounded answer generation with inline numbered citations.
ANSWER_PROMPT = (
    "You are a research assistant for laser-cladding scientific literature. Answer "
    "the user's question using ONLY the numbered sources below. Cite the sources you "
    "use inline with bracketed numbers like [1] or [2] that match the source numbers. "
    "If the sources do not contain the answer, say so plainly. Answer in the language "
    "of the question.\n\n"
    "{history_block}"
    "--- SOURCES ---\n{sources}\n\n--- QUESTION ---\n{question}\n--- ANSWER ---"
)
