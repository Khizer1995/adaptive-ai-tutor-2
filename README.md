# Cognitive Adaptive AI Tutor

An intelligent multi-agent learning platform that personalizes Python and DSA instruction using adaptive decision-making, RAG-grounded content, and real-time knowledge state tracking.

---

## Tech Stack

| Component | Technology |
|-----------|------------|
| **Workflow Orchestration** | LangGraph |
| **Multi-Agent Framework** | CrewAI |
| **LLM - Reasoning** | Google Gemini 2.0 Flash Lite |
| **LLM - Quiz/Fast** | Groq LLaMA-3.3-70B |
| **Vector Database** | ChromaDB |
| **Embeddings** | sentence-transformers (all-MiniLM-L6-v2) |
| **API Server** | FastAPI + Uvicorn |
| **Authentication** | Supabase |
| **Data Validation** | Pydantic v2 |

---

## System Architecture

**LangGraph 10-Node Pipeline:**

```
[file_manager] → [macro_decision] → [micro_decision] → [education_crew] 
    → [arbitration] → [validation] → [teacher_review] → [monitor] 
    → [knowledge_state] → [student_profile] → Loop/Exit
```

**Decision Logic:**
- **Macro Planner**: Assigns strategy (stabilize_foundations | guided_progression | advance_concepts) based on score, engagement, mastery
- **Micro Planner**: Weighted vote across 7 actions (increase_support, reinforce_basics, adjust_quiz, challenge_with_variation, advance_topic, reduce_support, increase_challenge)
- **Deterministic**: No randomness — same state → same decision

---

## Core Agents

### 1. Decision Engine
- **Macro**: Strategic policy selection using performance + engagement + trend
- **Micro**: Weighted scoring (25-30 points per action based on student state)
- **Arbitration**: Selects best crew proposal via confidence (60%) + cost (15%) + challenge (12.5%) + style (12.5%)

### 2. Education Crew
- **TutorAgent**: RAG query engineering → retrieval → LLM synthesis
- **PracticalAgent**: On-demand MCQ generation with difficulty scaling
- **TeacherPersonaAgent**: Style selection (Supportive Tutor | Balanced Coach | Challenging Mentor)

### 3. ValidationAgent
6-dimension quality checks: length, topic relevance, code presence, hallucination detection, quiz alignment, adaptive level fit

### 4. TeacherReviewAgent
Content approval gate (CLI manual review / API auto-approved)

### 5. MonitorAgent
Maps quiz scores → engagement levels (low <0.4, medium 0.4-0.75, high >0.75)

### 6. KnowledgeStateUpdater
Per-concept tracking: mastery = `0.7 * old + 0.3 * quiz_score`, confidence adjusts ±0.1/±0.15

### 7. StudentProfileAgent
Persists state to JSON with learning history, assessment scores, knowledge state

---

## RAG System

### Legacy Retriever
- ChromaDB semantic search with filters (concept_scope, source_priority, subject)
- Top-k retrieval with feedback-based re-ranking

### Layered KB - Adaptive Retriever
**Mastery-Aware Re-ranking:**
- Low mastery (<0.5): Prioritize OpenDSA concepts, penalize implementations
- Medium (0.5-0.7): Balanced mix
- High (>0.7): Prioritize PDF examples + implementations

**Score Formula:** `0.6 * cosine_sim + 0.25 * mastery_alignment + 0.15 * trend_boost`

---

## LLM Routing

**Task-Based Selection:**
- `deep_reasoning`, `concept_explanation` → Gemini 2.0 Flash Lite
- `quiz_generation`, `fast_response` → Groq LLaMA-3.3-70B
- **Fallback**: Gemini failure → auto-retry with Groq

---

## Metrics Calculated

### System Performance
| Metric | Value | Unit |
|--------|-------|------|
| RAG Latency | 0.4 | seconds |
| CrewAI Latency | 14.24 ± 4.97 | seconds |
| Validation Score | 0.72 ± 0.10 | 0-1 |
| Scaffolding Accuracy | 81.25% | percentage |
| Decision Iterations | 1.0 | count |

### Learning Outcomes
| Metric | Value |
|--------|-------|
| Participants | 1 |
| Mean Pretest Score | 0.82 |
| Mean Posttest Score | 0.79 |
| Raw Learning Gain | -0.03 |
| Hake Normalized Gain | -0.17 |

### User Study (n=4)
| Dimension | Score |
|-----------|-------|
| Usability | 4.45 / 5.0 |
| Adaptation | 4.31 / 5.0 |
| Engagement | 4.25 / 5.0 |

### Knowledge State Tracking
- **Mastery**: 0-1 scale, weighted update rule
- **Confidence**: 0-1 scale, ±0.1 on correct, -0.15 on incorrect
- **Scaffold Level**: high (<0.4) | medium (0.4-0.7) | low (>0.7)
- **Attempts**: Interaction count per concept

---

## Installation

```bash


# Install dependencies
pip install -r requirements.txt

# Configure environment (.env)
GOOGLE_API_KEY=your-gemini-key
GROQ_API_KEY=your-groq-key
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-key

# Initialize knowledge base
python scripts/ingest_pdf.py
python scripts/build_layered_kb.py
```

---

## Usage

### CLI Mode
```bash
python run_langgraph.py
```

### API Mode
```bash
uvicorn api_server:app --reload --port 8000

# Interactive docs: http://localhost:8000/docs
```

### Key Endpoints
- `POST /auth/signup` - Create account
- `POST /auth/login` - Authenticate
- `GET /student/state` - Get profile + knowledge state
- `POST /tutor/explain` - Request learning content
- `POST /quiz/generate` - Generate 3 MCQ questions
- `POST /quiz/submit` - Submit answers, update mastery

---

## Evaluation

**Generate Report:**
```bash
python scripts/generate_eval_report.py
```

**Output:** `data/eval_report.json` with system metrics, learning outcomes, user study results

**Key Findings:**
- 90.4% faster than baseline (14.24s vs 147.63s)
- 81.25% scaffolding accuracy (correct support adjustments)
- 4.34/5.0 average user satisfaction

---

## Key Features

✅ **Deterministic Decisions** - Weighted scoring, no randomness  
✅ **Mastery-Aware Retrieval** - Adapts chunks to student level  
✅ **Competing Proposals** - 3 agents compete, best selected via arbitration  
✅ **6-Dimension Validation** - Content quality before delivery  
✅ **Knowledge State Tracking** - Per-concept mastery/confidence  
✅ **Observable Decision Trail** - Complete logs for reproducibility  

---

## Project Structure

```
├── core/
│   ├── decision_engine.py      # Macro/micro decision + arbitration
│   ├── education_crew.py       # TutorAgent, PracticalAgent, TeacherPersona
│   ├── validation_agent.py     # Content quality checks
│   ├── knowledge_state_updater.py # Mastery/confidence updates
│   ├── langgraph_flow.py       # LangGraph state machine
│   ├── layered_kb/             # Adaptive retrieval system
│   ├── llm/                    # Gemini/Groq clients + router
│   └── rag/                    # Legacy retrieval system
├── data/
│   ├── eval_report.json        # Aggregated metrics
│   ├── vector_db/              # Legacy ChromaDB
│   └── vector_db_layered/      # Layered ChromaDB
├── logs/                       # JSONL structured logs
├── profiles/                   # Student JSON profiles
├── scripts/                    # Ingestion, testing, evaluation
└── api_server.py               # FastAPI application
```

---


---

## 🚀 Deployment

This project is configured for deployment on **Render** (backend) and **Vercel** (frontend).

### Quick Deploy

```bash
# Push to GitHub
git push origin develop

# Deploy backend to Render (see DEPLOYMENT_GUIDE.md)
# Deploy frontend to Vercel (see DEPLOYMENT_GUIDE.md)
```

### Deployment Documentation

- **📖 Full Guide**: See [`DEPLOYMENT_GUIDE.md`](./DEPLOYMENT_GUIDE.md) for complete step-by-step instructions
- **⚡ Quick Reference**: See [`QUICK_DEPLOY.md`](./QUICK_DEPLOY.md) for command shortcuts
- **📊 Summary**: See [`DEPLOYMENT_SUMMARY.md`](./DEPLOYMENT_SUMMARY.md) for overview

### Live URLs

- **Backend API**: Deploy to Render from `deploy` branch
- **Frontend**: Deploy to Vercel from `develop` branch
- **Auto-sync**: GitHub Action automatically syncs `develop` → `deploy`

### Environment Variables

Copy `.env.example` to `.env` and configure:

**Backend**:
- `GROQ_API_KEY`
- `GEMINI_API_KEY`
- `SUPABASE_URL`
- `SUPABASE_SERVICE_KEY`
- `JWT_SECRET_KEY`

**Frontend** (`ui/.env`):
- `VITE_API_BASE_URL`
- `VITE_SUPABASE_URL`
- `VITE_SUPABASE_ANON_KEY`

---
