# Graph Report - .  (2026-06-22)

## Corpus Check
- Corpus is ~8,558 words - fits in a single context window. You may not need a graph.

## Summary
- 338 nodes · 646 edges · 28 communities (18 shown, 10 thin omitted)
- Extraction: 59% EXTRACTED · 41% INFERRED · 0% AMBIGUOUS · INFERRED: 262 edges (avg confidence: 0.51)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_RAG Pipeline Core|RAG Pipeline Core]]
- [[_COMMUNITY_Vector Index Data Models|Vector Index Data Models]]
- [[_COMMUNITY_Frontend React Dependencies|Frontend React Dependencies]]
- [[_COMMUNITY_Architecture Documentation|Architecture Documentation]]
- [[_COMMUNITY_Database Manager & Analysis|Database Manager & Analysis]]
- [[_COMMUNITY_Text Extraction Layer|Text Extraction Layer]]
- [[_COMMUNITY_App Entry Points|App Entry Points]]
- [[_COMMUNITY_TypeScript App Config|TypeScript App Config]]
- [[_COMMUNITY_Metadata Extractor|Metadata Extractor]]
- [[_COMMUNITY_TypeScript Node Config|TypeScript Node Config]]
- [[_COMMUNITY_API Client Layer|API Client Layer]]
- [[_COMMUNITY_Document Splitter|Document Splitter]]
- [[_COMMUNITY_TypeScript Root Config|TypeScript Root Config]]
- [[_COMMUNITY_Frontend App Root|Frontend App Root]]
- [[_COMMUNITY_App Init|App Init]]
- [[_COMMUNITY_Domain Constants|Domain Constants]]
- [[_COMMUNITY_Prompt Templates Init|Prompt Templates Init]]
- [[_COMMUNITY_Metadata Prompts|Metadata Prompts]]
- [[_COMMUNITY_Frontend HTML Entry|Frontend HTML Entry]]
- [[_COMMUNITY_Frontend README|Frontend README]]

## God Nodes (most connected - your core abstractions)
1. `SearchHit` - 32 edges
2. `ChromaIndexer` - 30 edges
3. `MetadataExtractor` - 28 edges
4. `TextExtractor` - 28 edges
5. `DocumentAnalyzer` - 25 edges
6. `DocumentSplitter` - 23 edges
7. `DocumentMetadata` - 22 edges
8. `DuplicateDocumentError` - 21 edges
9. `RAGPipeline` - 20 edges
10. `DatabaseManager` - 19 edges

## Surprising Connections (you probably didn't know these)
- `LaserRAG Backend` --references--> `Conversational RAG Chat Module`  [EXTRACTED]
  backend/README.md → deliverables/architecture-rag-laser-cladding.md
- `LaserRAG Backend` --references--> `Pydantic Settings & Env Config`  [EXTRACTED]
  backend/README.md → deliverables/IMPLEMENTATION_PLAN.md
- `Docker Compose Infra Definition` --references--> `Redis (Queue + Pub/Sub)`  [EXTRACTED]
  docker-compose.yml → deliverables/architecture-rag-laser-cladding.md
- `ChromaIndexer` --uses--> `Chunk`  [INFERRED]
  backend/app/domain/chroma_indexer.py → backend/app/domain/models.py
- `ChromaIndexer` --uses--> `DocumentMetadata`  [INFERRED]
  backend/app/domain/chroma_indexer.py → backend/app/domain/models.py

## Import Cycles
- 1-file cycle: `backend/app/main.py -> backend/app/main.py`

## Hyperedges (group relationships)
- **7 Domain Modules forming RAGPipeline** — concept_textextractor, concept_documentanalyzer, concept_metadataextractor, concept_documentsplitter, concept_chromaindexer, concept_databasemanager, concept_ragpipeline [EXTRACTED 1.00]
- **Shared Infrastructure Dependencies (ChromaDB + PostgreSQL + LLM API)** — concept_chromadb, concept_postgresql, concept_llm_layer, concept_ragpipeline, concept_worker [EXTRACTED 1.00]
- **Async Document Indexing Subsystem** — concept_fastapi_gateway, concept_queue_arq, concept_redis, concept_worker, concept_indexing_flow [EXTRACTED 1.00]

## Communities (28 total, 10 thin omitted)

### Community 0 - "RAG Pipeline Core"
Cohesion: 0.09
Nodes (44): Path, SearchHit, Path, SearchHit, ChromaIndexer, DatabaseManager, DocumentAnalyzer, DocumentSplitter (+36 more)

### Community 1 - "Vector Index Data Models"
Cohesion: 0.09
Nodes (36): Chunk, DocumentMetadata, IndexedChunk, SearchHit, SearchHit, BaseModel, Embed ``chunks`` and upsert them with filterable metadata., Embed ``text`` and return the nearest chunks, optionally filtered. (+28 more)

### Community 2 - "Frontend React Dependencies"
Cohesion: 0.06
Nodes (31): dependencies, axios, react, react-dom, react-markdown, react-router-dom, @tanstack/react-query, devDependencies (+23 more)

### Community 3 - "Architecture Documentation"
Cohesion: 0.13
Nodes (31): LaserRAG Backend, Conversational RAG Chat Module, ChromaDB Vector Store (MiniLM-384, HNSW), ChromaIndexer Domain Module, Conversational RAG Query Flow, Relational Data Model (documents/citations/keywords/conversations/messages), DatabaseManager Domain Module, DocumentAnalyzer Domain Module (+23 more)

### Community 4 - "Database Manager & Analysis"
Cohesion: 0.11
Nodes (17): ABC, AnalysisResult, DocumentMetadata, IndexedChunk, AnalysisResult, DocumentType, InMemoryDatabaseManager, DatabaseManager — relational persistence interface (spec §3.1, §4 stage 6).  D (+9 more)

### Community 5 - "Text Extraction Layer"
Cohesion: 0.13
Nodes (17): Path, TextExtractor — raw file → normalized text + quality score (spec §4 stage 1)., Fraction of printable characters, penalized by replacement chars.          Gar, Extracts normalized text from a document file., Read ``path`` and return extracted text with quality metadata., Return (text, n_pages); n_pages is 0 when the format has no page concept., Trim, unify newlines, and collapse excessive blank lines., TextExtractor (+9 more)

### Community 6 - "App Entry Points"
Cohesion: 0.11
Nodes (15): create_app(), lifespan(), LaserRAG FastAPI application entrypoint., arq worker entrypoint., startup(), WorkerSettings, BaseSettings, BoundLogger (+7 more)

### Community 7 - "TypeScript App Config"
Cohesion: 0.10
Nodes (20): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, jsx, lib, module, moduleDetection, moduleResolution (+12 more)

### Community 8 - "Metadata Extractor"
Cohesion: 0.16
Nodes (11): DocumentMetadata, DocumentType, MetadataExtractor, MetadataExtractor — bibliographic metadata via LLM (spec §4 stage 3).  Feeds t, Extracts structured bibliographic metadata using an injected LLM., Return metadata for ``text``; fall back to the filename on failure., Last resort: derive a human title from the file stem., LLMClient (+3 more)

### Community 9 - "TypeScript Node Config"
Cohesion: 0.11
Nodes (17): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, lib, module, moduleDetection, moduleResolution, noEmit (+9 more)

## Knowledge Gaps
- **73 isolated node(s):** `BoundLogger`, `WorkerSettings`, `name`, `private`, `version` (+68 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **10 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `TextExtractor` connect `Text Extraction Layer` to `RAG Pipeline Core`, `Vector Index Data Models`?**
  _High betweenness centrality (0.050) - this node is a cross-community bridge._
- **Why does `ChromaIndexer` connect `RAG Pipeline Core` to `Vector Index Data Models`?**
  _High betweenness centrality (0.043) - this node is a cross-community bridge._
- **Why does `SearchHit` connect `Vector Index Data Models` to `RAG Pipeline Core`, `Metadata Extractor`?**
  _High betweenness centrality (0.043) - this node is a cross-community bridge._
- **Are the 30 inferred relationships involving `SearchHit` (e.g. with `Chunk` and `DocumentMetadata`) actually correct?**
  _`SearchHit` has 30 INFERRED edges - model-reasoned connections that need verification._
- **Are the 23 inferred relationships involving `ChromaIndexer` (e.g. with `Path` and `SearchHit`) actually correct?**
  _`ChromaIndexer` has 23 INFERRED edges - model-reasoned connections that need verification._
- **Are the 20 inferred relationships involving `MetadataExtractor` (e.g. with `Path` and `SearchHit`) actually correct?**
  _`MetadataExtractor` has 20 INFERRED edges - model-reasoned connections that need verification._
- **Are the 19 inferred relationships involving `TextExtractor` (e.g. with `Path` and `SearchHit`) actually correct?**
  _`TextExtractor` has 19 INFERRED edges - model-reasoned connections that need verification._