"""Async indexing queue (spec §4): arq enqueue + 6-stage job status.

The :class:`~app.queue.runner.StageRunner` runs the six indexing stages one at a
time, persisting each stage's output to a :class:`~app.queue.store.JobStore` so a
job can be retried from any stage. The arq worker (``app.worker``) is a thin shell
around it.
"""
