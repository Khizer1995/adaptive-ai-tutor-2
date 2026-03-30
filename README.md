# Cognitive Adaptive AI Tutor

An AI-driven adaptive learning system for Python built with a multi-agent architecture:
LangGraph for graph-based routing, CrewAI for agent orchestration, RAG (ChromaDB + sentence-transformers)
for curriculum retrieval, and Gemini for LLM synthesis.

## Team Responsibilities

| Member  | Area                              | Key Files |
|---------|-----------------------------------|-----------|
| Shazi   | Decision Engine + LangGraph Flow  | `core/decision_engine.py`, `core/langgraph_flow.py`, `run_langgraph.py` |
| Khizer  | Education Crew (Tutor, Practical, Persona) | `core/education_crew.py`, `core/tutor_agent.py`, `core/practical_agent.py`, `core/teacher_persona_agent.py` |
| Kishore | Student Profile + Monitor Agent   | `core/monitor_agent.py`, `core/profile_manager.py`, `core/student_profile_schema.py`, `profiles/` |
| Monish  | RAG Pipeline (PDF)                | `core/rag/`, `data/raw/`, `scripts/ingest_pdf.py` |

## Project Structure

```
Capstone_project/
|-- core/
|   |-- decision_engine.py
|   |-- langgraph_flow.py
|   |-- education_crew.py
|   |-- tutor_agent.py
|   |-- practical_agent.py
|   |-- teacher_persona_agent.py
|   |-- monitor_agent.py
|   |-- file_manager_agent.py
|   |-- student_profile_agent.py
|   |-- profile_manager.py
|   |-- student_profile_schema.py
|   |-- simulation.py
|   |-- validation_agent.py
|   |-- evaluation.py
|   |-- logging_utils.py
|   |-- rag/
|       |-- embedding_model.py
|       |-- ingestion.py
|       |-- vector_store.py
|       |-- retriever.py
|       |-- query_engineering.py
|-- data/
|   |-- raw/
|   |   |-- Python_Programming.pdf
|   |-- vector_db/
|-- profiles/
|-- scripts/
|-- tests/
|-- docs/
|-- logs/
|-- run_langgraph.py
|-- requirements.txt
|-- .env
```

## Setup

```powershell
cd "C:\Users\mohammed shazi\Desktop\SEM6\Capstone_project"
pip install -r requirements.txt
```

## Run Commands

1. Ingest Python Curriculum (run once)

```powershell
python scripts/ingest_pdf.py
```

2. Test Retrieval

```powershell
python scripts/test_retrieval.py
```

3. Run Full Simulation Loop (3 adaptive cycles)

```powershell
python -m core.simulation
```

4. Run LangGraph Flow

```powershell
python run_langgraph.py
```

## Environment Variables

Create `.env` in the project root:

```
GEMINI_API_KEY=your_gemini_api_key_here
```

## Architecture

```
File Manager -> Decision Engine -> Education Crew
                           |-- Tutor Agent (RAG + Gemini)
                           |-- Practical Agent (Adaptive Quiz)
                           |-- Teacher Persona Agent
                     -> Validation Agent
                     -> Monitor Agent -> Student Profile Agent
                     -> Loop or END (LangGraph)
```

## Documentation

See the `docs/` folder for architecture, evaluation, prompts, and reproducibility notes.
