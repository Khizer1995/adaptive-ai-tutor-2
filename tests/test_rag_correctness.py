from core.rag.query_engineering import RAGQueryEngineer
from core.rag.ingestion import PDFIngestionService


def test_query_engineering_adds_context():
    engineer = RAGQueryEngineer()
    query = "Explain Python variables"
    student_state = {"level": "beginner", "engagement": "low"}
    engineered = engineer.engineer(query, student_state)
    assert "[difficulty: beginner]" in engineered
    assert "engaging" in engineered


def test_chunking_overlap_behavior():
    service = PDFIngestionService("dummy.pdf")
    text = "one two three four five six seven eight nine ten"
    chunks = service.chunk_text(text, chunk_size=5, overlap=2)
    # Expect overlapping words between chunks
    assert len(chunks) >= 2
    assert "four five" in chunks[1]
