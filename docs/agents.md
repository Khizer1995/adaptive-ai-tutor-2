## Agents

Decision Engine:
- Computes weighted actions based on score, trend, engagement, and learning style.
- Outputs action routing for LangGraph.

Monitor Agent:
- Updates score, engagement, and progress based on action difficulty.
- Produces feedback and records learning history.

Validation Agent:
- Checks for presence of learning output.
- Logs validation status for academic review.

File Manager Agent:
- Ensures the RAG store is populated from teacher PDFs.
- Logs ingestion status and readiness.

Student Profile Agent:
- Persists student profile updates after each cycle.
