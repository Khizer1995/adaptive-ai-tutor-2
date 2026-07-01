from __future__ import annotations

import inspect
from dataclasses import asdict
from typing import Any, Dict, List, Tuple

from core.layered_kb.embeddings import EmbeddingProvider, build_embedder
from core.layered_kb.schema import StudentState
from core.layered_kb.vector_store import LayeredVectorStore
from core.rag.filter_normalizer import normalize_where_filter
from core.decision_engine import AblationConfig

_GLOBAL_ABLATION_CONFIG = AblationConfig()


def set_global_ablation_config(config: AblationConfig) -> None:
    global _GLOBAL_ABLATION_CONFIG
    _GLOBAL_ABLATION_CONFIG = config


def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    dot = sum(x * y for x, y in zip(v1, v2))
    norm1 = sum(x * x for x in v1) ** 0.5
    norm2 = sum(x * x for x in v2) ** 0.5
    if norm1 > 0 and norm2 > 0:
        return dot / (norm1 * norm2)
    return 0.0


class AdaptiveRetriever:
    def __init__(
        self,
        vector_store: LayeredVectorStore | None = None,
        embedder: EmbeddingProvider | None = None,
        ablation_config: AblationConfig | None = None,
    ) -> None:
        self.vector_store = vector_store or LayeredVectorStore()
        self.embedder = embedder or build_embedder("sentence-transformers")
        self.ablation_config = ablation_config or _GLOBAL_ABLATION_CONFIG

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
        
        # Check if vector_store.query accepts include parameter
        sig = inspect.signature(self.vector_store.query)
        kwargs = {}
        if "include" in sig.parameters:
            kwargs["include"] = ["documents", "metadatas", "embeddings"]

        try:
            results = self.vector_store.query(
                query_embedding=query_embedding,
                k=max(20, k * 4),
                where=normalized_where,
                **kwargs
            )
        except Exception:
            # Safe fallback for invalid/unsupported filter shapes.
            results = self.vector_store.query(
                query_embedding=query_embedding,
                k=max(20, k * 4),
                where=base_topic_filter,
                **kwargs
            )
        candidates = self._flatten_results(results)
        ranked = self._rerank(candidates, state, query_embedding)
        selected = self._diverse_select(ranked, k)
        return selected

    def _rerank(
        self,
        candidates: List[Dict[str, Any]],
        state: StudentState,
        query_embedding: List[float] | None = None,
    ) -> List[Tuple[float, Dict[str, Any]]]:
        ranked: List[Tuple[float, Dict[str, Any]]] = []
        mastery = state.student_mastery

        for item in candidates:
            meta = item["metadata"]
            
            # Compute cosine similarity
            doc_embedding = item.get("embedding")
            if doc_embedding is None and query_embedding is not None:
                doc_embedding = self.embedder.embed(item["document"])
            
            if query_embedding is not None and doc_embedding is not None:
                cosine_sim = cosine_similarity(query_embedding, doc_embedding)
            else:
                cosine_sim = 0.0

            # Compute original scoring parameters
            mastery_alignment = 0.0
            source = str(meta.get("source", ""))
            ctype = str(meta.get("type", "concept"))
            difficulty = str(meta.get("difficulty", "beginner"))

            if mastery < 0.5:
                if source == "opendsa":
                    mastery_alignment += 3.0
                if ctype == "concept":
                    mastery_alignment += 2.0
                if ctype == "example":
                    mastery_alignment += 1.5
                if ctype == "implementation":
                    mastery_alignment -= 1.5
                if difficulty in {"advanced", "intermediate"}:
                    mastery_alignment -= 0.8
            elif mastery <= 0.7:
                if source == "opendsa":
                    mastery_alignment += 1.4
                elif source.startswith("pdf_"):
                    mastery_alignment += 1.4
                if ctype == "concept":
                    mastery_alignment += 1.0
                if ctype == "example":
                    mastery_alignment += 1.2
                if ctype == "implementation":
                    mastery_alignment += 0.8
            else:
                if source.startswith("pdf_"):
                    mastery_alignment += 2.8
                if ctype == "implementation":
                    mastery_alignment += 1.8
                if ctype == "example":
                    mastery_alignment += 1.1
                if difficulty == "advanced":
                    mastery_alignment += 1.0

            if state.confidence < 0.6 and difficulty != "beginner":
                mastery_alignment -= 0.5

            trend_boost = 0.0
            if state.learning_trend.lower() == "fluctuating" and ctype == "concept":
                trend_boost += 0.6

            source_priority_boost = float(meta.get("source_priority", 1)) * 0.05

            if not self.ablation_config.use_mastery_rerank:
                # Rank purely by cosine similarity
                score = cosine_sim
            else:
                # Full system score formula:
                # 0.6 * cosine_sim + 0.25 * mastery_alignment + 0.15 * trend_boost + priority_boost
                score = 0.6 * cosine_sim + 0.25 * mastery_alignment + 0.15 * trend_boost + source_priority_boost

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
        embs = results.get("embeddings", [[]])
        embs_list = embs[0] if embs and len(embs) > 0 else []
        
        flat = []
        for i in range(min(len(ids), len(docs), len(metas))):
            item = {"id": ids[i], "document": docs[i], "metadata": metas[i]}
            if i < len(embs_list):
                item["embedding"] = embs_list[i]
            flat.append(item)
        return flat

    @staticmethod
    def _to_state(student_state: Dict[str, Any] | StudentState) -> StudentState:
        if isinstance(student_state, StudentState):
            return student_state
        return StudentState(**student_state)

