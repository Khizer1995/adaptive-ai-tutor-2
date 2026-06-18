from core.rag.ingestion import PDFIngestionService
from core.rag.vector_store import VectorStore


def print_metadata_sample(limit: int = 20) -> None:
    store = VectorStore()
    results = store.collection.get(limit=limit, include=["metadatas"])
    print("Metadata sample:")
    print(results.get("metadatas", []))


def reset_collection() -> None:
    store = VectorStore()
    name = store.collection.name
    store.client.delete_collection(name=name)
    store.collection = store.client.get_or_create_collection(name=name)
    print(f"Deleted and recreated collection: {name}")

if __name__ == "__main__":

    pdf_path = "data/raw/Python_Programming.pdf"

    print_metadata_sample(limit=20)
    reset_collection()
    ingestion = PDFIngestionService(pdf_path)
    ingestion.ingest(force_reingest=True)
    print_metadata_sample(limit=20)
