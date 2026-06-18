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
| `MonitorAgent` | Observes validated learning output and preserves quiz-driven score state without random score mutation |
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
`MonitorAgent` observes the validated learning output without applying random score variation. `KnowledgeStateUpdater` then applies quiz/assessment execution feedback to per-concept `mastery`, `confidence`, `attempts`, and `scaffold_level`.

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

## Current Implementation Progress

### Tech Stack in Use

| Area | Implemented Technology |
|---|---|
| Backend API | FastAPI, Pydantic v2 |
| Adaptive workflow | LangGraph `StateGraph` |
| Agent collaboration | Tutor, practical, teacher persona, teacher review, monitor, validation, and profile agents |
| LLM routing | Gemini for explanations/reasoning, Groq for fast quiz generation fallback |
| Retrieval | ChromaDB vector stores, `sentence-transformers`, PDF curriculum, and OpenDSA cached sources |
| Frontend | React, Vite, Tailwind CSS |
| Persistence | JSON student profiles in `profiles/`, JSONL logs in `logs/`, study data in `data/` |
| Evaluation | Pytest, Vite production build, `scripts/generate_eval_report.py` |

### Completed Backend Capabilities

- Deterministic macro and micro scaffolding decisions are implemented in `core/decision_engine.py`; every decision includes `decision_rationale`, fired weights, and JSONL evidence in `logs/decision_log.jsonl`.
- Random score mutation has been removed from `MonitorAgent`; learner score changes are driven by quiz, pre-test, and post-test submissions.
- Duplicate LangGraph teacher review node and conditional edge definitions were removed, leaving one clean review path.
- Learning-cycle metrics are collected through `core/metrics_collector.py`, including RAG latency, CrewAI latency, validation score, decision iterations, scaffolding direction, source types, and quiz pass rate.
- `ValidationAgent` returns a structured `ValidationResult` with pass/fail, per-check results, score, and flags, and logs each validation to `logs/validation_log.jsonl`.
- Pre-test and post-test endpoints are implemented at `/quiz/pretest` and `/quiz/posttest`; both reuse the quiz generation/scoring pipeline and tag submissions by assessment type.
- `core/knowledge_state_updater.py` computes `learning_gain` and Hake `normalized_learning_gain` from pre/post scores and stores them in the student profile.
- `GET /student/state` exposes assessment scores, learning gain, normalized learning gain, knowledge state, and progress fields.
- Study survey endpoints are implemented: `POST /study/survey` stores responses in `data/survey_responses.jsonl`, and `GET /study/results` returns aggregate Table 2-style means per question.
- Evaluation reporting is implemented through `scripts/generate_eval_report.py`, which reads metrics logs, validation logs, survey responses, and all student profiles, then exports `data/eval_report.json`.

### Completed Frontend Capabilities

- React UI supports topic selection, streamed tutor explanations, mastery heatmap, quick quizzes, and progress feedback.
- A "Start Learning Assessment" button triggers the pre-test before learning starts.
- A "Complete Assessment" button appears after topic completion and triggers the post-test.
- The UI displays pre-test score, post-test score, and learning gain after post-test completion.
- `ui/src/StudyQuestionnaire.jsx` provides a post-session survey with Usability, Trust, Engagement, and optional open-text sections.
- Survey responses are submitted from the UI to `/study/survey` after post-test completion.

### Evaluation Outputs Now Available

Run:

```bash
python scripts/generate_eval_report.py
```

The script prints:

- **SYSTEM METRICS** vs base paper benchmarks: RAG latency, CrewAI latency, validation score, decision iterations, and scaffolding accuracy.
- **LEARNING OUTCOMES**: mean pre-test, post-test, raw learning gain, and Hake normalized gain.
- **USER STUDY**: mean Likert dimensions for usability, adaptation, and engagement.

It also exports the same structured report to:

```bash
data/eval_report.json
```

### Not Started / Still Pending

- Multi-student API sessions are not implemented; the API still uses one active local `STUDENT_ID`.
- Authentication and user account management are not implemented.
- A teacher dashboard for manual review is not implemented; the API still auto-approves teacher review output for local/demo use.
- A frontend analytics dashboard for `data/eval_report.json` is not implemented yet.
- Deployment packaging with Docker or hosted infrastructure is not implemented.
- Real browser-based end-to-end tests are not implemented; current coverage is focused backend pytest plus frontend production build.

---

## Limitations

- **Limited non-quiz engagement signals** — `MonitorAgent` no longer applies random score variation; however, richer real-time behavioral signals such as time-on-task, hesitation, and hint usage are not yet captured.
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
