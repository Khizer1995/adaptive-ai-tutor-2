from typing import Any, Dict, List

from core.rag.filter_normalizer import normalize_where_filter
from core.rag.retriever import Retriever


class DummyEmbedder:
    def embed(self, text: str) -> List[float]:
        return [0.1, 0.2, 0.3]


class CaptureStore:
    def __init__(self) -> None:
        self.last_where = None

    def query(self, query_embedding, k=3, where=None):  # noqa: ANN001
        self.last_where = where
        return {"documents": [["doc1", "doc2", "doc3"]]}


class FailingThenSuccessStore:
    def __init__(self) -> None:
        self.calls = 0
        self.where_history: List[Any] = []

    def query(self, query_embedding, k=3, where=None):  # noqa: ANN001
        self.calls += 1
        self.where_history.append(where)
        if self.calls == 1:
            raise ValueError("Expected where to have exactly one operator")
        return {"documents": [["fallback-doc"]]}


def test_normalize_where_filter_single_field_unchanged() -> None:
    assert normalize_where_filter({"subject": "dsa"}) == {"subject": "dsa"}


def test_normalize_where_filter_multi_field_wrapped_with_and() -> None:
    assert normalize_where_filter({"concept": "hash_table", "subject": "dsa"}) == {
        "$and": [{"concept": "hash_table"}, {"subject": "dsa"}]
    }


def test_retriever_uses_normalized_where_filter() -> None:
    retriever = Retriever()
    retriever.embedder = DummyEmbedder()
    capture_store = CaptureStore()
    retriever.vector_store = capture_store

    _ = retriever.retrieve(
        query="hash table basics",
        concept_scope="hash_table",
        subject="dsa",
        k=2,
    )

    assert capture_store.last_where == {
        "$and": [{"concept": "hash_table"}, {"subject": "dsa"}]
    }


def test_retriever_falls_back_when_filtered_query_fails() -> None:
    retriever = Retriever()
    retriever.embedder = DummyEmbedder()
    fallback_store = FailingThenSuccessStore()
    retriever.vector_store = fallback_store

    results = retriever.retrieve(
        query="hash table basics",
        concept_scope="hash_table",
        subject="dsa",
        k=1,
    )

    assert results == ["fallback-doc"]
    assert fallback_store.calls == 2
    assert fallback_store.where_history[1] is None

