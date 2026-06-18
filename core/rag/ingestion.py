import uuid
from pypdf import PdfReader
from core.rag.embedding_model import LocalEmbeddingModel
from core.rag.vector_store import VectorStore


class PDFIngestionService:
    TOPIC_KEYWORD_MAP = {
        "stack": ["stack", "push", "pop", "peek", "lifo"],
        "queue": ["queue", "enqueue", "dequeue", "fifo", "front", "rear"],
        "linked_list": ["linked list", "node", "next pointer", "head", "tail"],
        "array": ["array", "index", "element", "contiguous"],
        "hash_table": ["hash", "bucket", "collision", "key-value", "key value"],
        "tree": ["binary tree", "root", "leaf", "traversal", "bst"],
        "sorting": ["bubble sort", "merge sort", "quick sort", "insertion sort"],
        "binary_search": ["binary search", "mid", "low", "high"],
    }
    def __init__(
        self,
        pdf_path,
        collection_name="python_course",
        source_type="teacher_pdf",
        subject="python_general",
    ):
        self.pdf_path = pdf_path
        self.embedder = None
        self.vector_store = VectorStore(collection_name=collection_name)
        self.source_type = source_type
        self.subject = subject

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
            metadatas.append(
                {
                    "source": self.pdf_path,
                    "chunk_index": i,
                    "source_type": self.source_type,
                    "subject": self.subject,
                    "concept": self._infer_concept(chunk, i),
                }
            )

        print("\nStoring in Chroma...")
        self.vector_store.add_documents(ids, embeddings, documents, metadatas)
        print("[PDFIngestionService] Ingestion complete.")

    def _infer_concept(self, chunk: str, index: int) -> str:
        text = str(chunk or "").lower()
        scores = {}
        for topic, keywords in self.TOPIC_KEYWORD_MAP.items():
            scores[topic] = sum(1 for kw in keywords if kw in text)
        best = max(scores, key=scores.get)
        if scores[best] > 0:
            return best
        return "general"
