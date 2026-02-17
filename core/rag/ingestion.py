import uuid
from pypdf import PdfReader
from core.rag.embedding_model import GeminiEmbeddingModel
from core.rag.vector_store import VectorStore


class PDFIngestionService:

    def __init__(self, pdf_path):
        self.pdf_path = pdf_path
        self.embedder = GeminiEmbeddingModel()
        self.vector_store = VectorStore()

    def extract_text(self):
        reader = PdfReader(self.pdf_path)
        text = ""

        for page in reader.pages:
            text += page.extract_text() + "\n"

        return text

    def chunk_text(self, text, chunk_size=500, overlap=50):
        words = text.split()
        chunks = []

        for i in range(0, len(words), chunk_size - overlap):
            chunk = " ".join(words[i:i + chunk_size])
            chunks.append(chunk)

        return chunks

    def ingest(self):

        print("Extracting text...")
        text = self.extract_text()

        print("Chunking...")
        chunks = self.chunk_text(text)

        print(f"Total chunks: {len(chunks)}")

        ids = []
        embeddings = []
        documents = []
        metadatas = []

        for chunk in chunks:
            embedding = self.embedder.embed(chunk)

            ids.append(str(uuid.uuid4()))
            embeddings.append(embedding)
            documents.append(chunk)
            metadatas.append({"source": "Python_Programming.pdf"})

        print("Storing in Chroma...")
        self.vector_store.add_documents(ids, embeddings, documents, metadatas)

        print("✅ Ingestion Complete!")
