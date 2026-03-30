## RAG Pipeline

1. PDF ingestion reads teacher-provided documents from `data/raw/`.
2. Text is chunked with overlap to preserve context.
3. Chunks are embedded using `all-MiniLM-L6-v2`.
4. ChromaDB stores embeddings in `data/vector_db/`.
5. Retriever selects top-k chunks for LLM synthesis.

Logs:
- `logs/rag.log` for query engineering and retrieval.
- `logs/langgraph_trace.jsonl` for trace events.
