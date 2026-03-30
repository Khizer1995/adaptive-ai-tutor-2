## Reproducibility Notes

1. Create and activate a virtual environment.
2. Install dependencies:
   - `pip install -r requirements.txt`
3. Add `GEMINI_API_KEY` to `.env`.
4. Place the course PDF at `data/raw/Python_Programming.pdf`.
5. Run ingestion once:
   - `python scripts/ingest_pdf.py`
6. Run the LangGraph demo:
   - `python run_langgraph.py`

Logs are generated in the `logs/` folder for traceability.
