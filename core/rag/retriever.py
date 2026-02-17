from core.rag.embedding_model import GeminiEmbeddingModel
from core.rag.vector_store import VectorStore


class Retriever:

    def __init__(self):
        self.embedder = GeminiEmbeddingModel()
        self.vector_store = VectorStore()

    def retrieve(self, query: str, k=3):

        query_embedding = self.embedder.embed(query)

        results = self.vector_store.query(query_embedding, k)

        return results["documents"][0]
