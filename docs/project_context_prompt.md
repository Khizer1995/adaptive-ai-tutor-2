You are joining an in-progress **Cognitive Adaptive AI Tutor** project.

## Project Objective
Build an adaptive tutoring system for DSA that personalizes content based on student state (mastery, confidence, trend, engagement, learning gain) using a multi-agent architecture + RAG.

## Critical Constraint
Do not modify or break existing backend logic, multi-agent flow, student model, decision engine, or evaluation pipeline.
Only extend functionality in an additive, modular way.

## Existing Codebase Context
- Core orchestration and agents live in `core/` (decision engine, tutor agent, monitor, profile/state updaters, etc.).
- Existing RAG pipeline lives in `core/rag/` and remains intact.
- Raw documents are in `data/raw/`.
- Vector DB for old RAG exists in `data/vector_db/`.

## What Has Been Implemented So Far (New Additive Layer)
A new isolated module `core/layered_kb/` was added for layered knowledge ingestion and adaptive retrieval:

1. `core/layered_kb/opendsa_scraper.py`
- Scrapes OpenDSA pages via `requests + BeautifulSoup`.
- Extracts heading-anchored sections (`h1`, `h2`, `h3`) and associated content.
- Builds concept-level chunks (not fixed token windows).

2. `core/layered_kb/pdf_ingestion.py`
- Parses PDFs with `pdfplumber`.
- Cleans repeated headers/footers/page numbers.
- Chunks semantically using heading-like boundaries.

3. `core/layered_kb/chunking.py`
- Topic normalization.
- Concept inference.
- Difficulty/type inference (`concept`, `example`, `implementation`).

4. `core/layered_kb/metadata.py`
- Metadata intelligence layer with source-priority logic.
- Beginner bias toward OpenDSA, depth from PDF layers.

5. `core/layered_kb/dependency_graph.py`
- Builds topic dependency graph:
  - `prerequisites`
  - `next_topics`

6. `core/layered_kb/embeddings.py`
- Embedding providers:
  - `sentence-transformers` (default)
  - Gemini embeddings (optional via API key).

7. `core/layered_kb/vector_store.py`
- Chroma persistent vector store for layered KB (`data/vector_db_layered`).

8. `core/layered_kb/retrieval.py`
- `AdaptiveRetriever.retrieve(query, student_state, k)` implemented.
- Mastery-aware retrieval rules:
  - `<0.5`: prioritize OpenDSA + simple conceptual chunks.
  - `0.5–0.7`: balanced OpenDSA/PDF + examples/basic implementation.
  - `>0.7`: prioritize PDF + advanced/implementation depth.
- Diversity guarantee in selected outputs:
  - at least one `concept`
  - at least one `example`
  - optional `implementation`

9. `core/layered_kb/builder.py`
- End-to-end build:
  - scrape OpenDSA
  - ingest PDFs
  - enrich metadata
  - persist chunks JSON
  - build dependency graph JSON
  - embed + upsert to Chroma

10. Scripts and docs
- Build script: `scripts/build_layered_kb.py`
- Retrieval smoke test: `scripts/test_layered_retrieval.py`
- Unit tests: `tests/test_layered_kb_retrieval.py` (passing)
- Documentation: `docs/layered-kb.md`
- OpenDSA URL list: `data/raw/opendsa_urls.txt` (validated)

## OpenDSA URL Validation Status
- User-provided URLs under `/ODSA/Books/Everything/<page>.html` were validated and returned 404.
- Correct working format is `/ODSA/Books/Everything/html/<page>.html`.
- `data/raw/opendsa_urls.txt` now contains verified working URLs.
- Some requested aliases were mapped to valid OpenDSA modules:
  - `StackRecurse` -> `StackRecur`
  - `QueueArray` -> `Queue`
  - `QueueSumm`/`StackSumm` -> `ListSumm` (linear structures summary)
  - `HashBucket` -> `BucketHash`
  - `HashSepChain` -> `OpenHash`
  - `HashDelete` -> `HashDel`
  - `HashAnalysis` -> `HashAnal`

## Current Input Sources
- PDFs in `data/raw/`:
  - `Hash Tables.pdf`
  - `Linked List.pdf`
  - `Stack and Queues in Python.pdf`
  - `_Array.pdf`
- OpenDSA URLs in `data/raw/opendsa_urls.txt`

## Expected Behavior of the Layered KB
- OpenDSA provides structure and beginner-friendly conceptual backbone.
- PDFs provide detailed explanations, examples, and implementation depth.
- Retrieval adapts to student state and maintains output diversity.

## What To Do Next
1. Keep all changes backward-compatible and additive.
2. Do not replace or alter old `core/rag/*` interfaces unless explicitly requested.
3. If extending retrieval, preserve student-state adaptation and metadata-based ranking.
4. Preserve clean metadata per chunk:
   - `topic`, `concept`, `source`, `difficulty`, `type`, `source_priority`, `content`.
5. Prefer production-safe changes with tests.

