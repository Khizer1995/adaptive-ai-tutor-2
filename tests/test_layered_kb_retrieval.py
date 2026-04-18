from typing import Any, Dict, List

from core.layered_kb.retrieval import AdaptiveRetriever


class DummyEmbedder:
    def embed(self, text: str) -> List[float]:
        return [0.1, 0.2, 0.3]


class DummyStore:
    def query(self, query_embedding: List[float], k: int = 12, where: Dict[str, Any] | None = None) -> Dict[str, Any]:
        return {
            "ids": [[
                "c1",
                "e1",
                "i1",
                "c2",
            ]],
            "documents": [[
                "Stack is a linear structure following LIFO.",
                "Example: push 10, push 20, pop returns 20.",
                "Python implementation using list append/pop.",
                "OpenDSA conceptual explanation of stack operations.",
            ]],
            "metadatas": [[
                {
                    "source": "opendsa",
                    "type": "concept",
                    "difficulty": "beginner",
                    "source_priority": 4,
                    "topic": "stack",
                    "concept": "definition",
                },
                {
                    "source": "pdf_stack_and_queues_in_python",
                    "type": "example",
                    "difficulty": "intermediate",
                    "source_priority": 3,
                    "topic": "stack",
                    "concept": "operations",
                },
                {
                    "source": "pdf_stack_and_queues_in_python",
                    "type": "implementation",
                    "difficulty": "intermediate",
                    "source_priority": 3,
                    "topic": "stack",
                    "concept": "implementation",
                },
                {
                    "source": "opendsa",
                    "type": "concept",
                    "difficulty": "beginner",
                    "source_priority": 4,
                    "topic": "stack",
                    "concept": "operations",
                },
            ]],
        }


def test_retrieve_enforces_diversity() -> None:
    retriever = AdaptiveRetriever(vector_store=DummyStore(), embedder=DummyEmbedder())
    results = retriever.retrieve(
        query="stack operations",
        student_state={
            "topic": "stack",
            "student_mastery": 0.45,
            "confidence": 0.5,
            "learning_trend": "fluctuating",
        },
        k=3,
    )
    types = {x["metadata"]["type"] for x in results}
    assert "concept" in types
    assert "example" in types


def test_beginner_prefers_opendsa_concept_first() -> None:
    retriever = AdaptiveRetriever(vector_store=DummyStore(), embedder=DummyEmbedder())
    results = retriever.retrieve(
        query="stack basics",
        student_state={
            "topic": "stack",
            "student_mastery": 0.3,
            "confidence": 0.9,
            "learning_trend": "steady",
        },
        k=2,
    )
    assert results[0]["metadata"]["source"] == "opendsa"
    assert results[0]["metadata"]["type"] == "concept"

