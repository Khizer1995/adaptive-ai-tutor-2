## Data Pipeline

Inputs:
- `data/raw/Python_Programming.pdf`
- Student profiles in `profiles/*.json`

Processing:
- PDF ingestion, chunking, embedding.
- Vector store in `data/vector_db/`.
- Retrieval during tutoring and quiz creation.

Outputs:
- Updated student profiles.
- Logs in `logs/` for traceability and evaluation.
