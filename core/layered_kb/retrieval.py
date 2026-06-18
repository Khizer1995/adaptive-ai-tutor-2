from __future__ import annotations

from dataclasses import asdict
from typing import Any, Dict, List, Tuple

from core.layered_kb.embeddings import EmbeddingProvider, build_embedder
from core.layered_kb.schema import StudentState
from core.layered_kb.vector_store import LayeredVectorStore
from core.rag.filter_normalizer import normalize_where_filter


class AdaptiveRetriever:
    def __init__(
        self,
        vector_store: LayeredVectorStore | None = None,
        embedder: EmbeddingProvider | None = None,
    ) -> None:
        self.vector_store = vector_store or LayeredVectorStore()
        self.embedder = embedder or build_embedder("sentence-transformers")

    def retrieve(
        self,
        query: str,
        student_state: Dict[str, Any] | StudentState,
        k: int = 5,
        where: Dict[str, Any] | None = None,
    ) -> List[Dict[str, Any]]:
        state = self._to_state(student_state)
        query_embedding = self.embedder.embed(query)
        base_topic_filter: Dict[str, Any] = {"topic": {"$eq": state.topic}}
        if where:
            where_clause = {"$and": [base_topic_filter, where]}
        else:
            where_clause = base_topic_filter
        normalized_where = normalize_where_filter(where_clause)
        try:
            results = self.vector_store.query(
                query_embedding=query_embedding,
                k=max(20, k * 4),
                where=normalized_where,
            )
        except Exception:
            # Safe fallback for invalid/unsupported filter shapes.
            results = self.vector_store.query(
                query_embedding=query_embedding,
                k=max(20, k * 4),
                where=base_topic_filter,
            )
        candidates = self._flatten_results(results)
        ranked = self._rerank(candidates, state)
        selected = self._diverse_select(ranked, k)
        return selected

    def _rerank(
        self, candidates: List[Dict[str, Any]], state: StudentState
    ) -> List[Tuple[float, Dict[str, Any]]]:
        ranked: List[Tuple[float, Dict[str, Any]]] = []
        mastery = state.student_mastery

        for item in candidates:
            meta = item["metadata"]
            score = 0.0
            source = str(meta.get("source", ""))
            ctype = str(meta.get("type", "concept"))
            difficulty = str(meta.get("difficulty", "beginner"))

            if mastery < 0.5:
                if source == "opendsa":
                    score += 3.0
                if ctype == "concept":
                    score += 2.0
                if ctype == "example":
                    score += 1.5
                if ctype == "implementation":
                    score -= 1.5
                if difficulty in {"advanced", "intermediate"}:
                    score -= 0.8
            elif mastery <= 0.7:
                if source == "opendsa":
                    score += 1.4
                elif source.startswith("pdf_"):
                    score += 1.4
                if ctype == "concept":
                    score += 1.0
                if ctype == "example":
                    score += 1.2
                if ctype == "implementation":
                    score += 0.8
            else:
                if source.startswith("pdf_"):
                    score += 2.8
                if ctype == "implementation":
                    score += 1.8
                if ctype == "example":
                    score += 1.1
                if difficulty == "advanced":
                    score += 1.0

            if state.confidence < 0.6 and difficulty != "beginner":
                score -= 0.5
            if state.learning_trend.lower() == "fluctuating" and ctype == "concept":
                score += 0.6
            score += float(meta.get("source_priority", 1)) * 0.05
            ranked.append((score, item))

        ranked.sort(key=lambda x: x[0], reverse=True)
        return ranked

    def _diverse_select(
        self, ranked: List[Tuple[float, Dict[str, Any]]], k: int
    ) -> List[Dict[str, Any]]:
        must_have = ["concept", "example"]
        selected: List[Dict[str, Any]] = []
        used = set()

        for needed in must_have:
            for score, item in ranked:
                if item["id"] in used:
                    continue
                if item["metadata"].get("type") == needed:
                    selected.append(self._as_output(score, item))
                    used.add(item["id"])
                    break

        for score, item in ranked:
            if len(selected) >= k:
                break
            if item["id"] in used:
                continue
            selected.append(self._as_output(score, item))
            used.add(item["id"])

        if len(selected) < k:
            for score, item in ranked:
                if len(selected) >= k:
                    break
                if item["id"] in used:
                    continue
                selected.append(self._as_output(score, item))
                used.add(item["id"])
        return selected[:k]

    @staticmethod
    def _as_output(score: float, item: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "chunk_id": item["id"],
            "score": round(score, 4),
            "content": item["document"],
            "metadata": item["metadata"],
        }

    @staticmethod
    def _flatten_results(results: Dict[str, Any]) -> List[Dict[str, Any]]:
        ids = results.get("ids", [[]])[0]
        docs = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]
        return [
            {"id": ids[i], "document": docs[i], "metadata": metas[i]}
            for i in range(min(len(ids), len(docs), len(metas)))
        ]

    @staticmethod
    def _to_state(student_state: Dict[str, Any] | StudentState) -> StudentState:
        if isinstance(student_state, StudentState):
            return student_state
        return StudentState(**student_state)

