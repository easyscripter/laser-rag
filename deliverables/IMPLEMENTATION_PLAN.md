# LaserRAG — Implementation Plan (working copy)

> Temporary working copy of the phased implementation plan, kept in-repo for ongoing development.
> Source spec: [`../deliverables/architecture-rag-laser-cladding.md`](../deliverables/architecture-rag-laser-cladding.md).

## Context

A RAG system over scientific literature on laser cladding. All domain/AI logic lives on the Python
backend; a thin React SPA talks to the assistant. Greenfield monorepo — the 7 domain modules (spec §3.1)
are implemented from scratch per the spec.

The work is split into phases; each delivers a verifiable vertical slice. Spec decisions are final;
this document describes *how* to implement them.

### Decisions / deviations (confirmed with the user)

- **PostgreSQL from the start** (not SQLite) — async SQLAlchemy + asyncpg. Matches the spec's "Postgres seam".
- **React 19 (stable) + TypeScript + Vite**; **axios** for REST (singleton via ES module, token key `accessToken`);
  native fetch/EventSource for SSE. **No Zustand. No frontend tests.**
- **Backend tests minimal** — only `DatabaseManager` rollback atomicity + one pipeline smoke.
- **Single shared root `.env`** (DB + backend + frontend) pulled into docker-compose: `env_file` for
  api/worker, `${...}` substitution for postgres/ports, build-args for the frontend.
- **No nginx** — frontend served by a light static server (`vite preview`). Multi-stage images.
- **No CI/CD** for now (skipped by request).
- `openapi-typescript` is an **optional** dev script (`npm run gen:api`), not required.

---

## Progress tracker

| Phase | Title | Status |
|---|---|---|
| 0 | Scaffold & tooling | ✅ Done |
| 1 | Domain modules (§3.1) | ✅ Done |
| 2 | Persistence (Postgres + Chroma) | ✅ Done |
| 3 | LLM layer (§3.2) | ✅ Done |
| 4 | Async indexing (arq, §4) | ✅ Done |
| 5 | Authentication | ✅ Done |
| 6 | Conversational RAG + SSE (§5, §7) | ✅ Done |
| 7 | Remaining REST (§6) | ⬜ |
| 8 | Frontend | ⬜ |
| 9 | Build & verification | ⬜ |

**Working mode:** one phase at a time, then stop and wait for an explicit command to continue.

---

## Stack

**Backend** (`backend/`): Python 3.12, **uv**, **FastAPI** (async), **Pydantic v2** + `pydantic-settings`,
**SQLAlchemy 2.0 async** + `asyncpg` (PostgreSQL), **Alembic**, **arq** + `redis`, `chromadb` (server mode),
`sentence-transformers` (MiniLM-384), **LangChain** + `langchain-openai`, auth via `pyjwt` + `passlib[argon2]`,
logs via `structlog`. Quality: **ruff** + **mypy --strict**. Tests minimal (`pytest`).

**Frontend** (`frontend/`): **React 19 + TypeScript + Vite**, **TanStack Query** (server state / job polling;
local UI state via React hooks, no Zustand), **React Router**, **Tailwind v4** + shadcn/ui, **axios**
(JWT/401 interceptors), `react-markdown` (safe render, no raw HTML). API types in `src/api/`.

**Infra:** single `docker-compose.yml` — `frontend`, `api` (uvicorn), `worker` (arq), `postgres`, `redis`,
`chromadb`. Multi-stage images. Volumes for Postgres + Chroma. Services reach each other by container name.

---

## Repo layout

```
LaserRAG/
├── backend/
│   ├── app/
│   │   ├── core/        # config (pydantic-settings, env §9), constants, logging  ✅
│   │   ├── domain/      # 7 modules from §3.1 (pure logic, no HTTP)               Phase 1
│   │   │   ├── text_extractor.py      # PDF/DOCX/ODT/TXT/MD + quality_score
│   │   │   ├── document_analyzer.py   # type by size + language by char mix
│   │   │   ├── metadata_extractor.py  # LLM→JSON, fallback ≤3
│   │   │   ├── document_splitter.py   # 800 words / overlap 150
│   │   │   ├── chroma_indexer.py      # MiniLM-384, HNSW, metadata filters
│   │   │   ├── database_manager.py    # interface + PostgreSQL impl (async SQLAlchemy)
│   │   │   └── pipeline.py            # RAGPipeline: index / search modes
│   │   ├── llm/         # ChatOpenAI factory per task + fallback chain (§3.2)      Phase 3
│   │   ├── chat/        # conversational RAG: condense, history window, persist    Phase 6
│   │   ├── queue/       # arq enqueue + 6-stage job status                         Phase 4
│   │   ├── api/         # routers, deps, SSE helpers (§6, §7)                       Phases 4–7
│   │   ├── db/          # SQLAlchemy models (§8), session, alembic/                 Phase 2
│   │   ├── schemas/     # Pydantic request/response DTOs
│   │   ├── main.py      # FastAPI assembly, CORS, security headers, /health        ✅
│   │   └── worker.py    # arq worker (6 stages, retry-from-stage)                   Phase 4
│   ├── tests/ · pyproject.toml · Dockerfile · .dockerignore                        ✅
├── frontend/
│   ├── src/
│   │   ├── api/         # axios singleton (JWT, 401) + SSE parser + types          ✅ (client)
│   │   ├── app/         # providers (Query + Router)                                ✅
│   │   ├── hooks/       # useSSEChat (token stream + citations event)              Phase 8
│   │   ├── features/{auth,chat,library,citations,stats}/                           Phase 8
│   │   └── components/  # one component per file, <Name>Props convention (§3.3)
│   ├── package.json · vite.config.ts · Dockerfile (multi-stage, no nginx)          ✅
├── deliverables/  · .env.example  · docker-compose.yml  · README.md  · .gitignore  ✅
```

---

## Cross-cutting security (all layers)

- **Auth:** JWT (access + refresh), **argon2** password hashing; roles `reader` / `curator` via FastAPI
  dependency guards; `tenant_id` in the token.
- **Input validation:** Pydantic on every endpoint; uploads — extension allowlist (pdf/docx/odt/txt/md),
  size limit, MIME check, SHA-256 dedup.
- **Output:** React escapes by default; `react-markdown` without raw HTML; `[1][2]` citations render as safe links.
- **DB:** parameterized SQLAlchemy queries only.
- **Transport/headers:** CORS to known origin; security-headers middleware; rate-limit on `/auth/login`
  and `/documents` (slowapi); secrets from env only (`.env` gitignored).
- **Multi-tenancy seams (§11):** `tenant_id` in all tables and in `DatabaseManager`/`ChromaIndexer`
  signatures; Chroma collection `corpus_{tenant_id}`.

---

## Phases

**Phase 0 — Scaffold & tooling.** ✅ Monorepo structure, uv project, ruff/mypy, pydantic-settings (env §9),
structured logging, FastAPI app + `/api/v1/health`, multi-stage Dockerfiles, single root `.env.example`,
docker-compose (postgres/redis/chromadb/api/worker/frontend), README. React 19 scaffolded via Vite CLI,
TanStack Query + axios + Router + Tailwind v4 wired. `ruff`/`mypy`/`pytest` green, frontend build green.

**Phase 1 — Domain modules (§3.1).** Implement the 7 modules as pure logic without HTTP: `TextExtractor`
(quality_score, warning <0.4), `DocumentAnalyzer` (type by size, language by char mix), `DocumentSplitter`
(800/150), `DatabaseManager` interface, `ChromaIndexer`, `MetadataExtractor` (LLM-dependent, mock LLM),
`RAGPipeline` (orchestrator, two modes). Minimal smoke test of the pipeline.

**Phase 2 — Persistence.** SQLAlchemy models for all tables (§8: documents/citations/keywords/conversations/
messages), Alembic init, **PostgreSQL** `DatabaseManager` impl with **atomic transaction + rollback**
(§4 stage 6), Chroma client integration (per-tenant collection).

**Phase 3 — LLM layer (§3.2).** `llm/` `ChatOpenAI` factory with configurable `base_url`, model choice by
task (`MODEL_FAST` / `MODEL_LONG_CTX` / `MODEL_FALLBACK`), fallback chain with ≤3 retries. Wire into
`MetadataExtractor`.

**Phase 4 — Async indexing (§4).** arq `worker.py`: 6 stages, each stage's output = next stage's input,
job status model (stage 1..6, status, quality_score?, warning?), **retry-from-stage N**; endpoints
`POST /documents` (multipart → 202 {job_id, doc_id}) and `GET /jobs/{job_id}`.

**Phase 5 — Authentication.** `POST /auth/login` → JWT + role; argon2; role guards; first-user seeder.

**Phase 6 — Conversational RAG + SSE (§5, §7).** `chat/`: condense follow-up (history-aware), history window
(`CHAT_HISTORY_WINDOW`, summarize on overflow), then **the 5 search steps exactly as in the article**
(detect language → translate → per-language search → merge/dedup/rank → generate). Key: retrieval uses the
*rewritten* query, generation uses the *original + history*. `POST /conversations/{id}/messages` returns an
SSE stream (`status`/`token`/`citations`/`done`); `messages.citations_json` persists the binding for reproducibility.

**Phase 7 — Remaining REST (§6).** `GET /conversations/{id}`, `POST /conversations`, documents
(list/summary/delete), `POST /search`, `POST /search/metadata`, `GET /stats`.

**Phase 8 — Frontend.** Auth flow + protected routes; **Chat** (main screen) on the `useSSEChat` hook (token
stream → bubble, citations event → sources panel, clickable `[1][2]`); **Library** (list + upload + 6-stage
progress via `GET /jobs` polling, Retry-from-stage-N button); **Source/citations panel**; **Stats/Admin**.

**Phase 9 — Build & verification.** Full `docker-compose` (all services), static frontend serving, e2e smoke.

---

## Verification

- **Backend (minimal):** `uv run pytest` — `DatabaseManager` rollback atomicity (against a test Postgres) and
  one pipeline smoke with a mock LLM.
- **API (manual):** `httpx`/curl — login→JWT, upload→202→poll job to stage 6, SSE chat (event order
  status→token→citations→done).
- **Quality:** `ruff check`, `mypy --strict`. No frontend tests.
- **E2E (manual):** `docker compose up` → in the browser: login → upload PDF → wait for indexing → ask a
  question → see streamed answer + clickable citations → sources panel.
- **Timing references (spec):** article indexing 8–18 s / monograph 15–45 s; semantic search <100 ms; full
  answer 3–10 s.

## Open assumptions

1. **LLM endpoint:** real URL/key from env; mock for dev/tests. Provider (OpenAI / vLLM / Ollama) set in
   `.env`; code is provider-agnostic.
2. **v1 scope** per spec §13 non-goals, **except the DB**: Postgres is used immediately. Deferred: e5-large,
   OCR, auto-monitoring of publications, streaming interruption.
