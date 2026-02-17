from core.rag.ingestion import PDFIngestionService

if __name__ == "__main__":

    pdf_path = "data/raw/Python_Programming.pdf"

    ingestion = PDFIngestionService(pdf_path)
    ingestion.ingest()
