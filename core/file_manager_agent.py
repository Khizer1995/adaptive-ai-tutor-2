import os
from typing import Dict, Any

from core.logging_utils import get_logger, trace_event, Timer
from core.rag.ingestion import PDFIngestionService
from core.rag.vector_store import VectorStore


class FileManagerAgent:
    """
    File Manager Agent (AIA-PAL alignment)

    - Manages teacher-provided PDFs
    - Ensures RAG store is ready
    - Logs ingestion and validation status
    """

    def __init__(self, pdf_path: str = None, source_type: str = "teacher_pdf", subject: str = "python_general"):
        self.pdf_path = pdf_path or os.path.join("data", "raw", "Python_Programming.pdf")
        self.source_type = source_type
        self.subject = subject
        self.logger = get_logger("file_manager", "file_manager.log")

    def prepare_knowledge_base(self, force_reingest: bool = False) -> Dict[str, Any]:
        timer = Timer()
        status = "skipped"
        detail = "RAG store already initialized."

        if not os.path.exists(self.pdf_path):
            status = "failed"
            detail = f"PDF not found: {self.pdf_path}"
            self.logger.error(detail)
            trace_event("file_manager_error", {"detail": detail})
            return {
                "rag_ready": False,
                "status": status,
                "detail": detail,
            }

        # Check existing collection size
        store = VectorStore()
        existing = store.collection.count()
        if existing == 0 or force_reingest:
            service = PDFIngestionService(
                self.pdf_path,
                source_type=self.source_type,
                subject=self.subject,
            )
            service.ingest(force_reingest=force_reingest)
            status = "ingested"
            store = VectorStore()
            detail = f"Ingested PDF into vector store. chunks={store.collection.count()}"

        duration_ms = round(timer.elapsed_ms(), 2)
        self.logger.info(f"status={status} detail={detail} duration_ms={duration_ms}")
        trace_event(
            "file_manager_status",
            {
                "status": status,
                "detail": detail,
                "duration_ms": duration_ms,
            },
        )
        return {
            "rag_ready": True,
            "status": status,
            "detail": detail,
            "duration_ms": duration_ms,
        }
