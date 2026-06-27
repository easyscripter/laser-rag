"""Conversational RAG (spec §5, §7).

The :class:`~app.chat.engine.ChatEngine` runs the query flow — condense the
follow-up, cross-lingual retrieval, then a streamed grounded answer with
citations — emitting the SSE events the API layer relays to the client.
"""
