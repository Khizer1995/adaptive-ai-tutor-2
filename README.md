# 🧠 Cognitive Adaptive AI Tutor

An AI-driven adaptive learning system for Python built with a multi-agent architecture:
**LangGraph** for graph-based routing, **CrewAI** for agent orchestration, **RAG** (ChromaDB + sentence-transformers) for curriculum retrieval, and **Gemini** for LLM synthesis.

---

## 👥 Team Responsibilities

| Member  | Area                              | Key Files |
|---------|-----------------------------------|-----------|
| **Shazi**  | Decision Engine + LangGraph Flow | `core/decision_engine.py`, `core/langgraph_flow.py`, `run_langgraph.py` |
| **Khizer** | Education Crew (Tutor, Practical, Persona) | `core/education_crew.py`, `core/tutor_agent.py`, `core/practical_agent.py`, `core/teacher_persona_agent.py` |
| **Kishore** | Student Profile + Monitor Agent | `core/monitor_agent.py`, `core/profile_manager.py`, `core/student_profile_schema.py`, `profiles/` |
| **Monish** | RAG Pipeline (PDF)               | `core/rag/`, `data/raw/`, `scripts/ingest_pdf.py` |

---

## 📁 Project Structure

```
Capstone_project/
├── core/
│   ├── decision_engine.py          # Shazi  — adaptive routing rules
│   ├── langgraph_flow.py           # Shazi  — LangGraph graph definition
│   ├── education_crew.py           # Khizer — crew orchestrator
│   ├── tutor_agent.py              # Khizer — RAG + Gemini tutor
│   ├── practical_agent.py          # Khizer — adaptive quiz generator
│   ├── teacher_persona_agent.py    # Khizer — teaching style selector
│   ├── monitor_agent.py            # Kishore — engagement + level tracker
│   ├── profile_manager.py          # Kishore — JSON profile read/write
│   ├── student_profile_schema.py   # Kishore — StudentProfile dataclass
│   ├── simulation.py               # Integration — 3-cycle simulation loop
│   ├── validation_agent.py         # Content quality gate
│   └── rag/
│       ├── embedding_model.py      # Monish — sentence-transformers embedder
│       ├── ingestion.py            # Monish — PDF ingestion pipeline
│       ├── vector_store.py         # Monish — ChromaDB persistent store
│       ├── retriever.py            # Monish — top-k semantic retrieval
│       └── query_engineering.py   # Monish — query refinement
├── data/
│   ├── raw/
│   │   └── Python_Programming.pdf  # Python curriculum
│   └── vector_db/                  # ChromaDB persistent storage
├── profiles/
│   ├── KISH-001.json               # Kishore's profile
│   ├── SHAZ-001.json               # Shazi's profile
│   ├── KHIZ-001.json               # Khizer's profile
│   └── MONI-001.json               # Monish's profile
├── scripts/
│   ├── ingest_pdf.py               # Ingest Python PDF into ChromaDB
│   └── test_retrieval.py           # Test retrieval from Python collection
├── tests/
│   ├── test_decision_engine.py
│   ├── test_education_crew.py
│   ├── test_monitor_agent.py
│   ├── test_langgraph.py
│   └── test_simulation.py
├── run_langgraph.py                # Shazi — LangGraph entry point
├── requirements.txt
└── .env                            # GEMINI_API_KEY=...
```

---

## ⚙️ Setup

```powershell
cd "c:\Users\mohammed shazi\Desktop\SEM6\Capstone_project"

# Install all dependencies
pip install -r requirements.txt
```

---

## 🚀 Run Commands

### 1. Ingest Python Curriculum (Monish) — Run once

```powershell
python scripts/ingest_pdf.py
```

### 2. Test Retrieval (Monish)

```powershell
python scripts/test_retrieval.py
```

### 3. Test Decision Engine (Shazi)

```powershell
python tests/test_decision_engine.py
```

### 4. Run Full Simulation Loop — 3 adaptive cycles (All team)

```powershell
python -m core.simulation
```

### 5. Run LangGraph Flow (Shazi)

```powershell
python run_langgraph.py
```

### 6. Test Profile Manager (Kishore)

```powershell
python core/profile_manager.py
```

---

## 🔑 Environment Variables

Create `.env` in the project root:

```
GEMINI_API_KEY=your_gemini_api_key_here
```

---

## 🏗️ Architecture

```
Student State → Decision Engine → Education Crew
                                    ├── TutorAgent      (RAG + Gemini)
                                    ├── PracticalAgent  (Adaptive Quiz)
                                    └── TeacherPersonaAgent (Style)
                               → Validation Agent
                               → Monitor Agent → (update state / promote level)
                               → Loop or END (LangGraph)
```
                         ├── TutorAgent      (RAG + Gemini)
                                    ├── PracticalAgent  (Adaptive Quiz)
                                    └── TeacherPersonaAgent (Style)
                               → Validation Agent
                               → Monitor Agent → (update state / promote level)
                               → Loop or END (LangGraph)
```