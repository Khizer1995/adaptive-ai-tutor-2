# Cognitive Adaptive AI Tutor

## Overview

The **Cognitive Adaptive AI Tutor** is a multi-agent, AI-powered personalized learning system designed to teach students **Python programming** and **Data Structures & Algorithms (DSA)** in an adaptive, context-aware manner.

Traditional e-learning systems deliver the same content to every student regardless of performance, pace, or learning style. This system solves that problem by continuously analyzing each student's score, engagement level, learning trend, and concept mastery — then dynamically adjusting what to teach, how to teach it, and how hard to make it. Every learning cycle produces content grounded in real curriculum material retrieved from a vector database, synthesized by an LLM, and validated before delivery.

---

## Features

- **Adaptive Decision Engine** — Selects the next pedagogical action (e.g., `increase_support`, `advance_topic`, `reinforce_basics`) using a weighted scoring model that factors in performance score, engagement, learning trend, and learning style.
- **Two-Level Planning** — A macro planner sets a strategic learning policy (`stabilize_foundations`, `guided_progression`, `advance_concepts`) while a micro planner selects the precise next action within that policy.
- **RAG-Grounded Content** — Curriculum content is ingested from PDF and OpenDSA sources into ChromaDB and retrieved at inference time using `sentence-transformers` embeddings, ensuring responses are grounded in actual material.
- **Layered Adaptive Retrieval** — A dedicated `AdaptiveRetriever` for DSA topics re-ranks retrieved chunks based on the student's mastery, confidence, and learning trend — prioritizing conceptual explanations for low-mastery students and implementation-level content for high-mastery ones.
- **Multi-Agent Education Crew** — Three agents collaborate per learning cycle: a `TutorAgent` for content generation, a `PracticalAgent` for quiz creation, and a `TeacherPersonaAgent` for teaching style adaptation.
- **Proposal Arbitration** — The `DecisionEngine` scores competing crew proposals and selects the most appropriate one based on the active action and student learning style.
- **Dual LLM Routing** — A `ModelRouterAgent` routes tasks to **Google Gemini 2.0 Flash Lite** (deep reasoning, concept explanation) or **Groq LLaMA-3.3-70B** (quiz generation, fast responses), with automatic Gemini → Groq fallback on failure.
- **Teacher Review Gate** — Generated content passes through a `TeacherReviewAgent` before delivery; rejected content halts the pipeline at that cycle.
- **Knowledge State Tracking** — Per-concept `mastery`, `confidence`, `attempts`, and `scaffold_level` are updated each cycle using execution feedback from the monitor.
- **Persistent Student Profiles** — Student state (progress, scores, history, knowledge state) is saved to JSON profiles after each cycle.
- **React Frontend + FastAPI Backend** — A full-stack interface exposes `/tutor/explain`, `/quiz/generate`, and `/quiz/submit` endpoints consumed by a Vite + React UI.
- **Structured Logging & Tracing** — All node transitions, decisions, RAG retrievals, and LLM calls are logged to structured JSONL trace files for observability.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Workflow Orchestration | LangGraph (StateGraph) |
| Multi-Agent Framework | CrewAI |
| LLM — Reasoning | Google Gemini 2.0 Flash Lite (`google-generativeai`) |
| LLM — Quiz / Fast | Groq LLaMA-3.3-70B (`groq`) |
| Vector Database | ChromaDB (persistent) |
| Embeddings | `sentence-transformers` — `all-MiniLM-L6-v2` |
| PDF Ingestion | `pypdf`, `pdfplumber` |
| Web Scraping | `beautifulsoup4`, `requests` (OpenDSA) |
| API Server | FastAPI |
| Frontend | React (Vite), Tailwind CSS |
| Data Validation | Pydantic v2 |
| Environment | `python-dotenv` |
| Testing | `pytest` |

---

## System Architecture / Design

The system is structured as a **LangGraph state machine** where each node is a distinct agent or decision step. State flows through the graph as a plain Python dictionary, making the entire pipeline inspectable and traceable at every node boundary.

```
┌─────────────────────────────────────────────────────────────────┐
│                     LANGGRAPH ADAPTIVE FLOW                     │
│                                                                 │
│  [file_manager] → [macro_decision] → [micro_decision]           │
│                                             │                   │
│                          ┌──────────────────┴──────────┐        │
│                          ▼                             ▼        │
│                   [education_crew]              [monitor]       │
│                          │                             │        │
│                   [arbitration]                        │        │
│                          │                             │        │
│                   [validation]                         │        │
│                          │                             │        │
│                   [teacher_review] ──────────→ [monitor]        │
│                                                        │        │
│                                              [knowledge_state]  │
│                                                        │        │
│                                              [student_profile]  │
│                                                        │        │
│                                        score < 0.85 → loop      │
│                                        score ≥ 0.85 → END       │
└─────────────────────────────────────────────────────────────────┘
```

### Component Roles

| Component | Role |
|---|---|
| `FileManagerAgent` | Checks if vector DB is populated; ingests PDF curriculum if empty |
| `DecisionEngine` | Macro planner (strategy) + micro planner (action) + proposal arbitrator |
| `EducationCrew` | Orchestrates Tutor, Practical, and TeacherPersona agents; submits proposals |
| `TutorAgent` | Builds engineered RAG query → retrieves chunks → calls LLM router → returns content |
| `PracticalAgent` | Generates topic-and-style-aware seed quiz questions |
| `TeacherPersonaAgent` | Selects persona (Supportive Tutor / Balanced Coach / Challenging Mentor) |
| `ValidationAgent` | Confirms `learning_path` is non-empty; marks `validation_status` |
| `TeacherReviewAgent` | Approves or halts content based on review queue rules |
| `MonitorAgent` | Adjusts `last_score` and `engagement` based on challenge level; appends to `learning_history` |
| `KnowledgeStateUpdater` | Applies execution feedback to per-concept mastery/confidence/scaffold fields |
| `StudentProfileAgent` | Persists updated student state to `profiles/<student_id>.json` |
| `ModelRouterAgent` | Routes LLM calls to Gemini or Groq; handles Gemini → Groq fallback |
| `AdaptiveRetriever` (Layered KB) | Mastery-aware re-ranking and diverse chunk selection for DSA topics |

---

## How It Works

**Step 1 — Knowledge Base Preparation**  
On startup, `FileManagerAgent` checks whether the ChromaDB vector store is populated. If not, it ingests the PDF curriculum (`data/raw/Python_Programming.pdf`) and OpenDSA content, chunks them, generates `sentence-transformers` embeddings, and stores them with typed metadata (`source`, `type`, `difficulty`, `concept`).

**Step 2 — Macro Planning**  
`DecisionEngine.decide_macro_plan()` reads the student's `last_score`, `learning_history`, and per-concept `knowledge_state` to assign a strategic policy:
- `stabilize_foundations` (score < 0.45 or declining trend)
- `guided_progression` (moderate mastery)
- `advance_concepts` (mastery > 0.75 and confidence > 0.70)

**Step 3 — Micro Decision**  
`DecisionEngine.decide_next_step()` runs a weighted vote across 7 possible actions using score, engagement, trend, learning style, and the macro policy. The highest-weight action wins and determines which next node to route to.

**Step 4 — Education Crew Execution**  
If routed to `education_crew`, all three agents run:
- `TutorAgent` engineers the RAG query → retrieves top-k chunks (via `AdaptiveRetriever` for DSA, legacy `Retriever` for Python) → sends context + query to the LLM router → returns synthesized content.
- `PracticalAgent` generates 3 quiz questions adapted to the action and learning style.
- `TeacherPersonaAgent` assigns a teaching persona based on score and engagement.

Each agent submits a **proposal** (scored by confidence, execution cost, challenge level, and style alignment).

**Step 5 — Arbitration & Validation**  
`DecisionEngine.arbitrate_crew_proposals()` selects the highest-scoring proposal. `ValidationAgent` confirms content is non-empty.

**Step 6 — Teacher Review**  
`TeacherReviewAgent` reviews the validated output. If approved, the cycle continues; if rejected, the graph terminates at `END` for that cycle.

**Step 7 — Monitor & Knowledge Update**  
`MonitorAgent` simulates interaction outcome: adjusts `last_score` relative to `challenge_level`, updates engagement tier (low / medium / high), and appends to `learning_history`. `KnowledgeStateUpdater` then updates per-concept `mastery`, `confidence`, `attempts`, and `scaffold_level`.

**Step 8 — Profile Persistence & Loop Control**  
`StudentProfileAgent` saves the updated state to disk. If `last_score < 0.85`, the graph loops back to `macro_decision` for another cycle; otherwise it exits.

---

## Setup & Installation

### Prerequisites
- Python 3.10+
- Node.js 18+ (for the UI)
- API keys for **Google Gemini** and **Groq**

### Backend

```bash
# Clone the repository
git clone <repo-url>
cd Capstone_project

# Create and activate a virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Linux/macOS

# Install dependencies
pip install -r requirements.txt

# Configure environment variables
# Create a .env file in the project root:
GEMINI_API_KEY=your_gemini_api_key_here
GROQ_API_KEY=your_groq_api_key_here

# Ingest curriculum into the vector database (one-time)
python -m scripts.ingest_pdf

# Start the API server
uvicorn api_server:app --reload --port 8000
```

### Frontend

```bash
cd ui
npm install
npm run dev
# Runs on http://localhost:5173
```

### Run Standalone (without UI)

```bash
# Run the adaptive simulation (3 cycles)
python -m core.simulation

# Run the full LangGraph flow
python run_langgraph.py
```

---

## Usage

### Via the React UI
1. Open `http://localhost:5173` in your browser.
2. Select a topic from the available DSA or Python curriculum.
3. The tutor generates an explanation grounded in the curriculum.
4. Take the 3-question MCQ quiz. Submit your answer.
5. The system updates your knowledge state and adapts the next session.

### Via the REST API

**Get student state:**
```bash
GET http://localhost:8000/student/state
```

**Request a topic explanation:**
```bash
POST http://localhost:8000/tutor/explain
Content-Type: application/json

{ "topic": "stack" }
```

**Generate a quiz:**
```bash
POST http://localhost:8000/quiz/generate
Content-Type: application/json

{ "topic": "stack" }
```

**Submit a quiz answer:**
```bash
POST http://localhost:8000/quiz/submit
Content-Type: application/json

{
  "question": "What is the time complexity of a stack push operation?",
  "selected_answer": "O(1)",
  "correct_answer": "O(1)",
  "topic": "stack"
}
```

**Sample Simulation Output:**
```
==================== CYCLE 1 ====================
Level      : beginner
Topic      : Python variables
Score      : 0.30
Engagement : medium
Decision   : {'action': 'increase_support', 'next_node': 'education_crew', ...}

[LLM Synthesis]
Simple Explanation:
Python variables are containers that store data values...

Monitor    : Observed steady performance in this interaction.
Learning Gain (this cycle): 0.12
```

---

## Challenges Faced

- **ChromaDB filter compatibility** — ChromaDB's `$in` operator requires a specific query shape. Misformed `where` filters caused silent retrieval failures; a `filter_normalizer.py` was built to normalize all filters before passing them to the store.
- **LLM response reliability** — Gemini occasionally returns empty content or exceeds rate limits. A full fallback chain (Gemini → Groq → template) was required to keep the pipeline always producing output.
- **Quiz grounding** — Generating MCQs that are consistent with what the student was actually taught (not hallucinated) required restricting quiz retrieval to `delivered_chunk_ids` — the set of chunks already shown in the explanation step.
- **LangGraph state mutation** — LangGraph's state dict is passed by reference between nodes. Unintentional in-place mutations in one node would corrupt state visible in downstream nodes; careful use of `.copy()` and explicit state key assignments was necessary.
- **Proposal scoring without ground truth** — The arbitration step scores competing agent proposals without any real student feedback signal at that moment. The scoring heuristic (confidence, cost, challenge level, style alignment) had to be tuned empirically across simulated runs.
- **Layered KB mastery thresholds** — Calibrating the re-ranking score deltas in `AdaptiveRetriever` so that chunk type priorities (concept vs. example vs. implementation) meaningfully changed with mastery bands required iterative simulation testing.

---

## Limitations

- **Simulated engagement signals** — `MonitorAgent` currently infers performance from `challenge_level` using random perturbations, not from actual student quiz answers in the LangGraph loop. Real-time answer grading is only wired in through the API's `/quiz/submit` endpoint.
- **Single active student** — The API server hardcodes `STUDENT_ID = "KISH-001"`. Supporting concurrent multi-student sessions would require session-scoped state management.
- **Fixed curriculum scope** — The system currently supports a predefined set of Python (9 topics) and DSA (7 topics) concepts. Adding new subjects requires extending curriculum files and re-ingesting the vector database.
- **No authentication** — There is no user authentication layer. The API is open and intended for local or lab use only.
- **Teacher review is auto-approved via API** — In the API server, `TeacherReviewAgent.review` is monkey-patched to auto-approve all content, bypassing the actual review logic.
- **Embedding model is CPU-bound** — `all-MiniLM-L6-v2` runs on CPU by default; on large corpora, ingestion and query latency will be noticeable without GPU acceleration.

---

## Future Improvements

- **Real quiz grading in the LangGraph loop** — Replace the simulated score update in `MonitorAgent` with actual answer evaluation using the submitted quiz responses from the frontend.
- **Multi-student session support** — Refactor the API server to be stateless per request and load student state dynamically based on a session token or student ID passed in the request.
- **Spaced repetition scheduling** — Incorporate a forgetting-curve-based scheduler to resurface weak concepts at optimal review intervals using the `learning_history` data already being tracked.
- **Streaming LLM responses** — Replace blocking LLM calls with SSE or WebSocket streaming to improve perceived response speed in the UI.
- **Expanded subject coverage** — Add new subject modules (e.g., databases, OS concepts) by ingesting additional PDFs and extending the curriculum lists without changing core agent logic.
- **Human-in-the-loop teacher review** — Build a teacher dashboard where actual educators can review flagged content instead of the current auto-approval patch.
- **Evaluation dashboard** — Surface `logs/evaluation.jsonl` and `logs/langgraph_trace.jsonl` data in the UI as real-time learning analytics (accuracy trend, mastery heatmap, decision trace).
- **Containerization** — Package the backend and frontend into Docker containers with a `docker-compose` setup to simplify deployment.

---

## Conclusion

The Cognitive Adaptive AI Tutor is a working implementation of a closed-loop adaptive learning system. It combines multi-agent orchestration, retrieval-augmented generation, mastery-aware content selection, and two-level pedagogical planning into a unified pipeline. Rather than treating all students the same, it makes a fresh, evidence-based decision every cycle about what to teach and at what difficulty — and it does so using curriculum content the student has already been exposed to. The result is a system that behaves like a tutor that actually pays attention.
