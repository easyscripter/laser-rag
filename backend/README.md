# LaserRAG — Backend

FastAPI backend for LaserRAG, a RAG system over laser-cladding scientific literature.

## Stack

Python 3.12 · FastAPI (async) · Pydantic v2 · SQLAlchemy 2.0 async + asyncpg (PostgreSQL) ·
Alembic · arq + Redis · ChromaDB · sentence-transformers (MiniLM-384) · LangChain · structlog.
Tooling: **uv**, **ruff**, **mypy --strict**, **pytest**.

## Local development

```bash
cd backend
cp .env.example .env          # adjust LLM_API_KEY etc.
uv sync                       # create venv + install deps (incl. dev group)
uv run uvicorn app.main:app --reload
```

Health check: `GET /api/v1/health` · API docs: `/api/v1/docs`.

## Quality & tests

```bash
uv run ruff check .
uv run mypy app
uv run pytest
```

## Layout

```
app/
  core/        config (pydantic-settings), constants, structured logging
  domain/      7 domain modules + RAGPipeline      (Phase 1)
  llm/         LangChain ChatOpenAI factory          (Phase 3)
  queue/       arq enqueue + job status              (Phase 4)
  chat/        conversational RAG (condense, SSE)    (Phase 6)
  api/         routers, deps, SSE helpers            (Phases 4–7)
  db/          SQLAlchemy models + Alembic           (Phase 2)
  schemas/     Pydantic DTOs
  main.py      app assembly
  worker.py    arq worker                            (Phase 4)
```

Built phase-by-phase — see `../../.claude/plans/` for the implementation plan.
