from typing import List, Dict, Any, cast
from core.rag.embedding_model import LocalEmbeddingModel
from core.rag.vector_store import VectorStore
from core.logging_utils import get_logger, trace_event, Timer



class Retriever:
    """
    Retrieves top-k relevant chunks from ChromaDB for the Python course.
    """

    def __init__(self) -> None:
        self.embedder = LocalEmbeddingModel()
        self.vector_store = VectorStore()
        self.logger = get_logger("rag", "rag.log")

    def retrieve(
        self,
        query: str,
        k: int = 3,
        feedback: Dict[str, float] = None,
        concept_scope: str = "",
        source_priority: str = "",
        subject: str = "",
    ) -> List[str]:
        """
        Retrieve and re-rank chunks. Optionally use feedback to penalize poor chunks.
        feedback: dict mapping chunk text to penalty score (lower is better)
        """
        timer = Timer()
        query_embedding: List[float] = cast(List[float], self.embedder.embed(query))
        where = {}
        if concept_scope:
            where["concept"] = concept_scope
        if source_priority:
            where["source_type"] = source_priority
        if subject:
            where["subject"] = subject
        results: Dict[str, Any] = cast(
            Dict[str, Any],
            self.vector_store.query(query_embedding, k * 2, where=where if where else None),
        )
        documents: Any = results.get("documents", [])
        chunks = []
        if isinstance(documents, list) and len(documents) > 0:
            first_page = documents[0]
            if isinstance(first_page, list):
                chunks = [str(doc) for doc in first_page]

        # --- Chunk re-ranking ---
        if feedback:
            # Penalize chunks with negative feedback
            def feedback_score(chunk):
                return feedback.get(chunk, 0)
            chunks = sorted(chunks, key=feedback_score)

        # Simple: return top-k after re-ranking
        selected = chunks[:k]
        duration_ms = round(timer.elapsed_ms(), 2)
        self.logger.info(
            f"query_len={len(query)} k={k} concept={concept_scope} source={source_priority} "
            f"subject={subject} retrieved={len(selected)} duration_ms={duration_ms}"
        )
        trace_event(
            "rag_retrieve",
            {
                "k": k,
                "retrieved": len(selected),
                "duration_ms": duration_ms,
            },
        )
        return selected
