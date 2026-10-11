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

## Installation & Setup

### 1. Clone and Navigate
```bash
git clone <repository-url>
cd Capstone_project
```

### 2. Backend Setup

```bash
# Create and activate virtual environment
# Windows:
python -m venv venv
venv\Scripts\activate

# Mac/Linux:
# python3 -m venv venv
# source venv/bin/activate

# Install Python dependencies
pip install -r requirements.txt

# Configure environment variables
# Copy .env.example to .env and fill in your keys:
# - GOOGLE_API_KEY (Gemini API)
# - GROQ_API_KEY (Groq API)
# - SUPABASE_URL (Your Supabase project URL)
# - SUPABASE_SERVICE_KEY (Supabase service key)
# - JWT_SECRET_KEY (Secret key for JWT tokens)

# Initialize knowledge base (optional - for RAG system)
python scripts/ingest_pdf.py
python scripts/build_layered_kb.py
```

### 3. Frontend Setup

```bash
# Navigate to UI directory
cd ui

# Install Node.js dependencies
npm install

# Configure frontend environment
# Copy ui/.env.example to ui/.env and set:
# - VITE_API_BASE_URL=http://127.0.0.1:8765
# - VITE_SUPABASE_URL (same as backend)
# - VITE_SUPABASE_ANON_KEY (Supabase anon key)
```

---

## Running the Application

### Development Mode (Local)

You'll need two terminal windows running simultaneously.

#### Terminal 1: Backend Server (Port 8765)
```bash
# From project root directory
# Make sure virtual environment is activated
uvicorn api_server:app --host 127.0.0.1 --port 8765 --reload
```

**Backend will run on:**
- API: http://localhost:8765
- Interactive Docs: http://localhost:8765/docs
- ReDoc: http://localhost:8765/redoc

#### Terminal 2: Frontend Server (Port 5173)
```bash
# From project root directory
cd ui
npm run dev
```

**Frontend will run on:**
- App: http://localhost:5173
- (Check terminal output for exact port if different)

### Testing the Setup

1. Open http://localhost:5173 in your browser
2. Click "Sign Up" to create a test account
3. Log in and start learning!

### CLI Mode (Backend Only)
```bash
# Run the LangGraph pipeline without the web UI
python run_langgraph.py
```

---

## Key API Endpoints

### Authentication
- `POST /auth/signup` - Create new account
- `POST /auth/login` - Login and get JWT token
- `POST /auth/logout` - Logout
- `GET /auth/me` - Get current user info

### Learning
- `GET /student/state` - Get student profile and progress
- `GET /student/topics` - Get all topics with mastery levels
- `POST /tutor/explain` - Request adaptive learning content
- `POST /quiz/generate` - Generate practice quiz questions
- `POST /quiz/submit` - Submit quiz answers and update mastery

### Assessments
- `POST /quiz/pretest` - Take pretest for a topic
- `POST /quiz/posttest` - Take posttest after learning

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
