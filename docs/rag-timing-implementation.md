# RAG Latency Timing Implementation

## Overview
RAG (Retrieval-Augmented Generation) latency is now properly measured from the moment retrieval starts until the retrieved content is available for the LLM to process.

## Implementation Details

### 1. Timing Start Point
**Location**: `core/tutor_agent.py` → `retrieve_context_chunk_records()`

```python
from time import perf_counter
rag_start_time = perf_counter()  # Start timer at retrieval entry
```

This captures the start time immediately when the retrieval function is called.

### 2. Timing End Points
The timer stops at the return of retrieved chunks in **three different retrieval paths**:

#### Path A: Hybrid Retrieval (PDF + OpenDSA)
- Uses `HybridRetriever` for DSA subjects
- Retrieves from both PDF chunks and web sources
- Timer stops when hybrid records are returned

#### Path B: Layered Retrieval (Adaptive)
- Uses `AdaptiveRetriever` with layered knowledge base
- Applies adaptive filtering based on student mastery
- Timer stops when cleaned results are returned

#### Path C: Legacy Fallback
- Uses basic retriever when other paths fail
- Timer stops when legacy chunks are assembled

### 3. Latency Storage
```python
rag_latency_ms = round((perf_counter() - rag_start_time) * 1000.0, 2)
student_state["_rag_latency_ms"] = rag_latency_ms
```

The latency is stored in `student_state` for later metrics collection.

### 4. Metrics Collection
**Location**: `core/langgraph_flow.py` → `profile_node()`

```python
rag_latency_ms = state.get("student_state", {}).get("_rag_latency_ms", 0.0)

log_learning_cycle_metrics(
    timings={
        "rag_latency_ms": rag_latency_ms,
        "crewai_latency_ms": state.get("crewai_latency_ms", 0.0),
        "e2e_latency_ms": e2e_latency_ms,
    },
    ...
)
```

Extracted from student_state and logged to `logs/metrics_log.jsonl`.

### 5. Evaluation Report
**Location**: `scripts/generate_eval_report.py`

```python
rag_seconds = [number / 1000 for number in values(metrics, "rag_latency_ms")]
```

Converts milliseconds to seconds and compares with base paper benchmark (147.63s).

## What's Measured

The RAG latency captures:
- ✅ Query engineering and preprocessing
- ✅ Vector search execution
- ✅ Embedding computation time
- ✅ Metadata filtering
- ✅ Result ranking and selection
- ✅ OpenDSA web scraping (if cached, retrieval is instant)
- ✅ Content blending (PDF + web sources)
- ✅ Adaptive difficulty adjustment

The RAG latency does **NOT** include:
- ❌ LLM generation time (tracked separately as `crewai_latency_ms`)
- ❌ Validation or post-processing
- ❌ Student profile updates

## Base Paper Comparison

| Metric | Your System | Base Paper | Improvement |
|--------|-------------|------------|-------------|
| RAG Latency | Measured in real-time | 147.63s | Now quantified |

**Previous Issue**: RAG latency was showing as 0.0s because it was pulling from `rag_status` which tracked file manager operations, not actual retrieval time.

**Current Implementation**: RAG latency is now properly timed from retrieval start to content delivery, capturing all three retrieval paths (hybrid, layered, legacy).

## Verification

To verify RAG timing is working:

1. Run a learning cycle:
   ```bash
   python run_langgraph.py
   ```

2. Check the logs:
   ```bash
   tail -n 20 logs/rag.log | grep "rag_retrieve_completed"
   ```

3. Check metrics:
   ```bash
   tail -n 5 logs/metrics_log.jsonl | jq '.rag_latency_ms'
   ```

4. Generate evaluation report:
   ```bash
   python scripts/generate_eval_report.py
   ```

Look for non-zero `rag_latency_seconds` in the system metrics section.

## Expected Results

- **Development**: 50-500ms (local vector DB)
- **Production**: 100-2000ms (with network latency)
- **Base Paper**: 147,630ms (2.5 minutes - significantly slower)

Your implementation should be **99%+ faster** than the base paper due to:
- Efficient vector database (ChromaDB)
- Local caching of OpenDSA content
- Optimized chunking and indexing
- Pre-computed embeddings
