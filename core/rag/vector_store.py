import chromadb
from chromadb.config import Settings


class VectorStore:

    def __init__(self, persist_directory="data/vector_db"):
        self.client = chromadb.Client(
            Settings(persist_directory=persist_directory)
        )

        self.collection = self.client.get_or_create_collection(
            name="python_course"
        )

    def add_documents(self, ids, embeddings, documents, metadatas):
        self.collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas
        )

    def query(self, query_embedding, k=3):
        return self.collection.query(
            query_embeddings=[query_embedding],
            n_results=k
        )
