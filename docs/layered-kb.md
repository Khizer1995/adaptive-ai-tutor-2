## Layered Knowledge Base System

This module is additive and does not modify existing `core/rag/*` or agent logic.

### Added structure

- `core/layered_kb/schema.py`: chunk and student-state schema
- `core/layered_kb/opendsa_scraper.py`: OpenDSA scraping and concept chunking
- `core/layered_kb/pdf_ingestion.py`: PDF parsing, cleaning, semantic chunking
- `core/layered_kb/metadata.py`: metadata intelligence and source priority
- `core/layered_kb/dependency_graph.py`: optional topic dependency graph
- `core/layered_kb/embeddings.py`: sentence-transformers and Gemini embedding providers
- `core/layered_kb/vector_store.py`: Chroma persistence for layered KB
- `core/layered_kb/builder.py`: end-to-end ingestion pipeline
- `core/layered_kb/retrieval.py`: adaptive retrieval by student state
- `scripts/build_layered_kb.py`: runnable build script
- `scripts/test_layered_retrieval.py`: quick manual retrieval check

### Run ingestion

```bash
python scripts/build_layered_kb.py --pdf-dir data/raw --opendsa-urls-file data/raw/opendsa_urls.txt
```

If `data/raw/opendsa_urls.txt` is not present, script defaults to Stack/Queue/Hash OpenDSA pages.

### Outputs

- `data/processed/layered_chunks.json`
- `data/processed/topic_dependency_graph.json`
- Chroma collection `layered_dsa_kb` in `data/vector_db_layered`

### Adaptive retrieval

```python
from core.layered_kb.retrieval import AdaptiveRetriever

retriever = AdaptiveRetriever()
results = retriever.retrieve(
    query="Explain stack operations with examples",
    student_state={
        "topic": "stack",
        "student_mastery": 0.62,
        "confidence": 0.59,
        "learning_trend": "fluctuating",
    },
    k=4,
)
```

