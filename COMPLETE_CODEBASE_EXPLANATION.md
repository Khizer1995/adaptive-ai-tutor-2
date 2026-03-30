# Complete Codebase Explanation

This document explains every file in the repository, what it implements, and what the outputs look like when you run the system. It follows the actual structure of the codebase.

---

## Root Files

### `.env`
- **Purpose:** Stores environment variables (not tracked in git).
- **Key value:** `GEMINI_API_KEY` for Gemini API access.
- **Output behavior:** If the key is missing or invalid, the TutorAgent will fall back to template responses instead of live Gemini output.

### `.gitignore`
- **Purpose:** Git ignore rules for virtual environments, caches, logs, and other generated files.
- **Notable entries:** `venv/`, `data/vector_db/`, `logs/`.

### `README.md`
- **Purpose:** Project overview, setup instructions, and architecture diagram.
- **Output behavior:** Not executed; provides documentation.

### `requirements.txt`
- **Purpose:** Python dependencies for the project.
- **Main libs:** `langgraph`, `crewai`, `chromadb`, `sentence-transformers`, `google-generativeai`, `pypdf`.

### `run_langgraph.py`
- **Purpose:** Runs the LangGraph adaptive flow end‑to‑end.
- **What it does:**
  - Builds an initial student state.
  - Invokes `adaptive_graph` from `core/langgraph_flow.py`.
  - Prints final student state and last crew output.
  - Logs a lightweight evaluation summary.
- **Output snippet:**
  ```
  ============================================================
    Cognitive Adaptive AI Tutor — LangGraph Flow
  ============================================================

  Initial Student State:
    student_id: KISH-001
    level: beginner
    current_topic: None
    ...

  Running LangGraph adaptive flow...

  ============================================================
  FINAL STUDENT STATE:
  ============================================================
    student_id: KISH-001
    level: beginner
    current_topic: Python variables
    ...

  --- Last Crew Output ---
    Teacher Style : Balanced Coach: Provide structured explanations...
    Quiz          : [...]
    Validation    : passed
  ```

---

## Core Package (`core/`)

### `core/__init__.py`
- **Purpose:** Marks the `core` directory as a Python package.
- **Output behavior:** None.

### `core/logging_utils.py`
- **Purpose:** Shared logging utilities.
- **What it provides:**
  - File-based loggers in `logs/`.
  - `log_jsonl()` for structured JSONL logs.
  - `trace_event()` for LangGraph trace lines in `logs/langgraph_trace.jsonl`.
  - `Timer` for measuring durations.

### `core/decision_engine.py`
- **Purpose:** Chooses the next action based on performance and trend.
- **Key logic:**
  - Analyzes learning trend from the last 3 scores.
  - Weighted scoring across actions.
  - Returns `{next_node, action, weights, reason}`.
- **Output snippet (from simulation):**
  ```
  Decision   : {'next_node': 'education_crew',
                'action': 'adjust_quiz',
                'weights': {...},
                'reason': "Selected 'adjust_quiz' based on score=0.71 ..."}
  ```

### `core/education_crew.py`
- **Purpose:** Orchestrates Tutor, Practical, Persona agents.
- **How it works:**
  - Always selects a teacher persona.
  - Generates content and quizzes based on decision action.
  - Attaches decision context into `crew_output`.
- **Output snippet:**
  ```
  crew_output = {
    "learning_path": "<LLM or fallback text>",
    "quiz": ["Q1...", "Q2...", "Q3..."],
    "teacher_style": "Balanced Coach: ...",
    "rag_chunks": [...],
    "engineered_query": "...",
    "decision": {...}
  }
  ```

### `core/tutor_agent.py`
- **Purpose:** Generates learning content (RAG + Gemini).
- **Flow:**
  - Selects current topic (or next topic).
  - Builds a style‑aware query.
  - Uses `RAGQueryEngineer` to refine query.
  - Retrieves chunks from ChromaDB.
  - Calls Gemini model `gemini-2.0-flash-lite`.
  - Falls back to template if Gemini fails.
- **Output snippet (fallback):**
  ```
  Simple Explanation:
  Python variables is a key concept in Python used to store and manipulate data.

  Code Example:
  x = 10
  name = "Alice"
  print(x, name)
  ```

### `core/practical_agent.py`
- **Purpose:** Generates quiz questions based on topic, level, learning style.
- **Output snippet:**
  ```
  [
    "What is Python variables?",
    "Write a simple example of Python variables.",
    "When would you use Python variables?"
  ]
  ```

### `core/teacher_persona_agent.py`
- **Purpose:** Selects teaching persona based on score + engagement.
- **Personas:** Supportive Tutor / Balanced Coach / Challenging Mentor.
- **Output snippet:**
  ```
  "Balanced Coach: Provide structured explanations, guided exercises..."
  ```

### `core/validation_agent.py`
- **Purpose:** Validates that learning output exists.
- **Logic:** If `learning_path` exists → `passed`, else `failed`.
- **Output snippet:**
  ```
  "validation_status": "passed"
  ```

### `core/monitor_agent.py`
- **Purpose:** Simulates student performance and updates state.
- **What it does:**
  - Adjusts score based on action type.
  - Updates engagement (low/medium/high).
  - Adds entry to `learning_history`.
  - Updates progress and level.
- **Output snippet:**
  ```
  Monitor    : Student progressing steadily.
  ```

### `core/profile_manager.py`
- **Purpose:** Loads/saves student JSON profiles in `profiles/`.
- **Output snippet:**
  ```
  [ProfileManager] Saved profile → profiles\KISH-001.json
  ```

### `core/student_profile_schema.py`
- **Purpose:** Canonical StudentProfile schema (Pydantic-like structure).
- **Fields:** student_id, name, level, progress, engagement, last_score, history, etc.

### `core/student_profile_agent.py`
- **Purpose:** Persists state via ProfileManager and logs the action.
- **Behavior:** Skips if `student_id` missing.

### `core/file_manager_agent.py`
- **Purpose:** Ensures PDF ingestion into vector DB is done before learning loop.
- **Behavior:**
  - Checks if `data/raw/Python_Programming.pdf` exists.
  - If vector DB empty → ingest.
  - Logs status to `logs/file_manager.log`.

### `core/rag/embedding_model.py`
- **Purpose:** Sentence-transformers embedding model (`all-MiniLM-L6-v2`).
- **Used by:** Retriever + ingestion.

### `core/rag/vector_store.py`
- **Purpose:** ChromaDB wrapper for persistent storage.
- **Storage:** `data/vector_db/`.

### `core/rag/ingestion.py`
- **Purpose:** Ingests PDF → chunks → embeddings → vector DB.
- **Output snippet:**
  ```
  Extracting text...
  Chunking...
  Total chunks: 312
  Storing in Chroma...
  ✅ Ingestion Complete!
  ```

### `core/rag/query_engineering.py`
- **Purpose:** Refines retrieval queries with level/engagement tags.
- **Output snippet:**
  ```
  "Explain Python variables for beginner level [difficulty: beginner] [make it more engaging]"
  ```

### `core/rag/retriever.py`
- **Purpose:** Embeds query + retrieves top‑k chunks from ChromaDB.
- **Output snippet:**
  ```
  Chunk 1:
  <text from Python_Programming.pdf>
  ```

### `core/langgraph_flow.py`
- **Purpose:** Defines the LangGraph state machine for the adaptive loop.
- **Nodes:**
  1. `file_manager`
  2. `decision`
  3. `education_crew`
  4. `validation`
  5. `monitor`
  6. `student_profile`
- **Routing:**
  - Decision → EducationCrew or Monitor
  - Profile → Continue or END (score threshold 0.85)
- **Trace Output:** Logs enter/exit of nodes to `logs/langgraph_trace.jsonl`.

### `core/evaluation.py`
- **Purpose:** Maps runtime data to evaluation criteria for reporting.
- **Outputs:** Writes to `logs/evaluation.jsonl`.
- **Fields:** accuracy, adaptability, response_time, workflow coordination, scaffolding status.

### `core/simulation.py`
- **Purpose:** Runs a 3‑cycle adaptive simulation loop.
- **Output snippet:**
  ```
  ==================== CYCLE 1 ====================
  --- New Cycle ---
  Level      : beginner
  Topic      : Python variables
  Score      : 0.3
  Engagement : medium
  Decision   : {...}

  [LLM Synthesis]
  Simple Explanation:
  ...
  Monitor    : Student progressing steadily.
  Learning Gain (this cycle): 0.15
  Accuracy (so far): 0.00
  Engagement Score (this cycle): 6
  ```

---

## Scripts (`scripts/`)

### `scripts/ingest_pdf.py`
- **Purpose:** One‑time ingestion of the PDF into ChromaDB.

### `scripts/test_retrieval.py`
- **Purpose:** Quick retrieval test to view top chunks for a query.
- **Output snippet:**
  ```
  --- Retrieved Chunks ---
  Chunk 1:
  ...
  ```

---

## Tests (`tests/`)

### `tests/show_graph.py`
- **Purpose:** Prints LangGraph nodes/edges.
- **Output snippet:**
  ```
  Nodes:
  - file_manager
  - decision
  - education_crew
  ...
  ```

### `tests/test_decision_engine.py`
- **Purpose:** Prints decisions for sample student states.

### `tests/test_education_crew.py`
- **Purpose:** Runs EducationCrew once and prints output.

### `tests/test_langgraph.py`
- **Purpose:** Calls `adaptive_graph.invoke` with a small state.

### `tests/test_monitor_agent.py`
- **Purpose:** Runs MonitorAgent directly with mock data.

### `tests/test_rag_correctness.py`
- **Purpose:** Validates query engineering and chunk overlap logic.

### `tests/test_simulation.py`
- **Purpose:** Runs 3 simulation cycles.

### `tests/test_student_lifecycle.py`
- **Purpose:** Tests profile creation, save, and reload.

---

## Docs (`docs/`)

These files are non-executable and describe the architecture and evaluation:
- `architecture.md` — system architecture.
- `agents.md` — agent roles.
- `crew.md` — education crew description.
- `data-pipeline.md` — ingestion + storage flow.
- `evaluation.md` — metrics mapping.
- `prompts.md` — prompt structure and personas.
- `rag.md` — retrieval pipeline.
- `reproducibility.md` — run steps.
- `state-diagrams.md` — Mermaid diagrams for flow + RAG.

---

## Legacy Sample (`hello_world/`)

This directory contains earlier prototype code (CrewAI + Pydantic schemas).
It is not wired into the main `core/` system.

Key files:
- `models.py` — basic `StudentProfile` schema.
- `profile_manager.py` — JSON save/load for profiles.
- `agents.py` / `monitoring_crew.py` — CrewAI Gemini-based monitor prototype.
- `tools.py` — sentiment-based frustration updater.
- `main.py`, `test_monitor.py`, `test_schema.py` — demos/tests.

---

## What the System Output Looks Like (Full Run)

Typical output from:
```
python -m core.simulation
```

```
============================================================
ADAPTIVE LEARNING SIMULATION (3 cycles)
============================================================

==================== CYCLE 1 ====================
--- New Cycle ---
Level      : beginner
Topic      : Python variables
Score      : 0.3
Engagement : medium
Decision   : {'next_node': 'education_crew', 'action': 'increase_support', ...}

[LLM Synthesis]
Simple Explanation:
Python variables are containers that store data values...

Monitor    : Student progressing steadily.
Learning Gain (this cycle): 0.12
Accuracy (so far): 0.00
Engagement Score (this cycle): 6
[ProfileManager] Saved profile → profiles\KISH-001.json
```

If Gemini fails, you’ll see fallback template responses instead of AI‑generated text.

---

## Log Files Generated

- `logs/langgraph_trace.jsonl` — node enter/exit events
  ```
  {"timestamp":"...","event":"node_enter","payload":{"node":"decision"}}
  ```
- `logs/crew.log` — crew actions and timings
- `logs/monitor.log` — monitor updates
- `logs/rag.log` — RAG query + retrieval metrics
- `logs/evaluation.jsonl` — evaluation metrics

---

## Summary

This codebase implements a full adaptive learning loop with:
- Decision engine (weighted routing)
- Multi-agent crew
- RAG‑enhanced tutoring via Gemini
- Monitoring and persistent student profiles
- LangGraph orchestration with traceable logs

The result is a repeatable, observable tutoring pipeline that can be run either as a **simulation** (`python -m core.simulation`) or as the **LangGraph flow** (`python run_langgraph.py`).
