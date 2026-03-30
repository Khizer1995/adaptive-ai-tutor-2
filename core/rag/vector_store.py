import chromadb


class VectorStore:

    def __init__(
        self,
        persist_directory: str = "data/vector_db",
        collection_name: str = "python_course",
        in_memory: bool = False,
    ):

        if in_memory:
            self.client = chromadb.Client()
        else:
            # Use PersistentClient for persistent storage
            self.client = chromadb.PersistentClient(
                path=persist_directory
            )

        self.collection = self.client.get_or_create_collection(
            name=collection_name
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
