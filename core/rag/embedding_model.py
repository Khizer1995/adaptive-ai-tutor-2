from sentence_transformers import SentenceTransformer


class LocalEmbeddingModel:
    """
    Local embedding model using sentence-transformers
    """

    def __init__(self):
        self.model = SentenceTransformer("all-MiniLM-L6-v2")

    def embed(self, text: str):
        return self.model.encode(text).tolist()
