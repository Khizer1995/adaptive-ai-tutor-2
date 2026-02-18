from core.rag.embedding_model import LocalEmbeddingModel
from core.rag.vector_store import VectorStore


class Retriever:

    def __init__(self):
        self.embedder = LocalEmbeddingModel()
        self.vector_store = VectorStore()

    def retrieve(self, query: str, k=3):

        query_embedding = self.embedder.embed(query)

        results = self.vector_store.query(query_embedding, k)

        documents = results.get("documents", [])

        # Chroma returns nested list
        if documents and len(documents) > 0:
            return documents[0]

        return []
