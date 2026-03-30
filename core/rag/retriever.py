from typing import List, Dict, Any, cast
from core.rag.embedding_model import LocalEmbeddingModel
from core.rag.vector_store import VectorStore



class Retriever:
    """
    Retrieves top-k relevant chunks from ChromaDB for the Python course.
    """

    def __init__(self) -> None:
        self.embedder = LocalEmbeddingModel()
        self.vector_store = VectorStore()

    def retrieve(self, query: str, k: int = 3, feedback: Dict[str, float] = None) -> List[str]:
        """
        Retrieve and re-rank chunks. Optionally use feedback to penalize poor chunks.
        feedback: dict mapping chunk text to penalty score (lower is better)
        """
        query_embedding: List[float] = cast(List[float], self.embedder.embed(query))
        results: Dict[str, Any] = cast(Dict[str, Any], self.vector_store.query(query_embedding, k*2))
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
        return chunks[:k]
