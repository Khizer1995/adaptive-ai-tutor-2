from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from core.delivery_tracker import get_delivered_topic_summary


class CurriculumNavigator:
    def __init__(
        self,
        chunks_path: str = "data/processed/layered_chunks.json",
        graph_path: str = "data/processed/topic_dependency_graph.json",
    ) -> None:
        self.chunks_path = Path(chunks_path)
        self.graph_path = Path(graph_path)
        self._chunks: List[Dict[str, Any]] | None = None
        self._graph: Dict[str, Dict[str, List[str]]] | None = None

    def ordered_concepts(self, topic: str) -> List[str]:
        chunks = [c for c in self._load_chunks() if str(c.get("topic", "")).strip() == topic]
        chunks.sort(key=lambda c: int(c.get("order_index", 0)))
        concepts: List[str] = []
        for chunk in chunks:
            concept = str(chunk.get("concept", "")).strip()
            if concept and concept not in concepts:
                concepts.append(concept)
        return concepts

    def first_concept(self, topic: str) -> str:
        concepts = self.ordered_concepts(topic)
        return concepts[0] if concepts else "fundamentals"

    def next_topic(self, topic: str) -> str:
        graph = self._load_graph()
        next_topics = (graph.get(topic, {}) or {}).get("next_topics", [])
        if next_topics:
            return str(next_topics[0])

        topics_in_order: List[str] = []
        for chunk in sorted(self._load_chunks(), key=lambda c: int(c.get("order_index", 0))):
            name = str(chunk.get("topic", "")).strip()
            if name and name not in topics_in_order:
                topics_in_order.append(name)
        if topic in topics_in_order:
            idx = topics_in_order.index(topic)
            if idx + 1 < len(topics_in_order):
                return topics_in_order[idx + 1]
        return topic

    def _load_chunks(self) -> List[Dict[str, Any]]:
        if self._chunks is not None:
            return self._chunks
        if not self.chunks_path.exists():
            self._chunks = []
            return self._chunks
        raw = json.loads(self.chunks_path.read_text(encoding="utf-8"))
        self._chunks = [x for x in raw if isinstance(x, dict)]
        return self._chunks

    def _load_graph(self) -> Dict[str, Dict[str, List[str]]]:
        if self._graph is not None:
            return self._graph
        if not self.graph_path.exists():
            self._graph = {}
            return self._graph
        raw = json.loads(self.graph_path.read_text(encoding="utf-8"))
        self._graph = raw if isinstance(raw, dict) else {}
        return self._graph


def build_next_recommendation(
    student_state: Dict[str, Any],
    topic: str,
    navigator: CurriculumNavigator | None = None,
) -> Dict[str, str]:
    nav = navigator or CurriculumNavigator()
    delivered = get_delivered_topic_summary(student_state, topic)

    confidence = float(
        (
            student_state.get("knowledge_state", {})
            .get("concepts", {})
            .get(topic, {})
            .get("confidence", student_state.get("last_score", 0.0))
        )
        or 0.0
    )

    if confidence < 0.55:
        review_concept = delivered["concepts"][-1] if delivered["concepts"] else nav.first_concept(topic)
        return {
            "label": "Review current concept",
            "topic": topic,
            "concept": review_concept,
            "reason": f"Confidence is still low ({confidence:.2f}); review before advancing.",
        }

    ordered_concepts = nav.ordered_concepts(topic)
    delivered_concepts = set(delivered["concepts"])
    for concept in ordered_concepts:
        if concept not in delivered_concepts:
            return {
                "label": "Read next concept",
                "topic": topic,
                "concept": concept,
                "reason": "You completed the current chunk with good confidence.",
            }

    next_topic = nav.next_topic(topic)
    if next_topic != topic:
        return {
            "label": "Read next concept",
            "topic": next_topic,
            "concept": nav.first_concept(next_topic),
            "reason": f"You completed core concepts in {topic} with good confidence.",
        }

    return {
        "label": "Practice this concept",
        "topic": topic,
        "concept": delivered["concepts"][-1] if delivered["concepts"] else "fundamentals",
        "reason": "Continue reinforcing this topic with one more practice pass.",
    }

