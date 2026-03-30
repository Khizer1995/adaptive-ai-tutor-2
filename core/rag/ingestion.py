import uuid
from pypdf import PdfReader
from core.rag.embedding_model import LocalEmbeddingModel
from core.rag.vector_store import VectorStore


class PDFIngestionService:

    def __init__(self, pdf_path, collection_name="python_course"):
        self.pdf_path = pdf_path
        self.embedder = None
        self.vector_store = VectorStore(collection_name=collection_name)

    def _get_embedder(self):
        if self.embedder is None:
            self.embedder = LocalEmbeddingModel()
        return self.embedder

    def extract_text(self):
        reader = PdfReader(self.pdf_path)
        text = ""
        for page in reader.pages:
            extracted = page.extract_text()
            if extracted:
                text += extracted + "\n"
        return text

    def chunk_text(self, text, chunk_size=500, overlap=50):
        words = text.split()
        chunks = []
        step = chunk_size - overlap
        for i in range(0, len(words), step):
            chunk = " ".join(words[i:i + chunk_size])
            if chunk.strip():
                chunks.append(chunk)
        return chunks

    def ingest(self, force_reingest=False):
        # Guard: skip if collection already has documents
        existing = self.vector_store.collection.count()
        if existing > 0 and not force_reingest:
            print(f"[PDFIngestionService] Collection already has {existing} docs. Skipping.")
            print("  Pass force_reingest=True to overwrite.")
            return

        print("Extracting text...")
        text = self.extract_text()

        print("Chunking...")
        chunks = self.chunk_text(text)
        print(f"Total chunks: {len(chunks)}")

        ids, embeddings, documents, metadatas = [], [], [], []

        for i, chunk in enumerate(chunks):
            print(f"  Embedding chunk {i + 1}/{len(chunks)}...", end="\r")
            embedding = self._get_embedder().embed(chunk)
            ids.append(str(uuid.uuid4()))
            embeddings.append(embedding)
            documents.append(chunk)
            metadatas.append({
                "source": self.pdf_path,
                "chunk_index": i
            })

        print("\nStoring in Chroma...")
        self.vector_store.add_documents(ids, embeddings, documents, metadatas)
        print("✅ Ingestion Complete!")
