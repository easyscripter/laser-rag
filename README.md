# LaserRAG

A RAG system over scientific literature on laser cladding. All domain/AI logic lives on the Python
backend; the React frontend is a thin client for talking to the assistant.

Architecture spec: [`deliverables/architecture-rag-laser-cladding.md`](deliverables/architecture-rag-laser-cladding.md).
Implementation plan (phased): `~/.claude/plans/`.

## Stack

| Layer | Technologies |
|---|---|
| Frontend | React 19 + TypeScript + Vite, TanStack Query, React Router, Tailwind v4, axios |
| Backend | Python 3.12, FastAPI (async), Pydantic v2, SQLAlchemy 2.0 + asyncpg |
| Data | PostgreSQL · ChromaDB (MiniLM-384, HNSW) · Redis |
| AI | LangChain (`ChatOpenAI`, configurable `base_url`), sentence-transformers |
| Queue | arq + Redis (async indexing) |

## Layout

```
LaserRAG/
├── backend/        FastAPI + domain + worker (uv, ruff, mypy)
├── frontend/       React 19 SPA (Vite)
├── deliverables/   architecture specification
├── .env.example    single shared env for all services
└── docker-compose.yml
```

## Run with Docker

```bash
cp .env.example .env        # fill in LLM_API_KEY etc.
docker compose up --build
```

Services: `frontend` :5173 · `api` :8000 · `postgres` · `redis` · `chromadb` · `worker`.
All read configuration from the shared root `.env` (api/worker via `env_file`, postgres/ports via
`${...}` substitution, frontend via build args).

Health check: `http://localhost:8000/api/v1/health` · UI: `http://localhost:5173`.

## Local development

```bash
# Backend
cd backend && uv sync && uv run uvicorn app.main:app --reload

# Frontend
cd frontend && npm install && npm run dev
```

## Status

Built **phase by phase** (Phase 0 — scaffolding and tooling complete). See each service's README for details.
