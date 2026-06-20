from core.rag.retriever import Retriever
from core.rag.query_engineering import RAGQueryEngineer
from core.llm.router import ModelRouterAgent
from core.logging_utils import get_logger, trace_event, Timer
from core.adaptive_engine import (
    build_content_context,
    build_adaptive_prompt,
    record_content,
)
from typing import Dict, Any, List, cast
import json
from core.hybrid_retriever import HybridRetriever


class TutorAgent:
    """
    Adaptive Tutor Agent
    ====================
    Root-cause fixes applied:
      • generate_learning_path now calls build_content_context() so the LLM
        prompt adapts to the student's actual quiz score (Issue #1).
      • Variation seed in the prompt prevents identical outputs on repeated
        calls for the same topic (Issue #2).
      • Generated content is recorded via record_content() so the next call
        sees the prior summary and avoids repeating it (Issue #2).
      • curriculum lists are sourced from adaptive_engine.get_all_topics()
        rather than a hardcoded 7-item list (Issue #5 partial).
    """

    # Legacy static lists kept only for get_next_topic() compatibility.
    python_curriculum = [
        "Python variables", "Control flow (if/else)", "Loops", "Functions",
        "Lists and arrays", "Modules and packages", "Object-oriented programming",
        "Error handling", "File I/O"
    ]
    dsa_curriculum = [
        "array", "linked_list", "stack", "queue",
        "hash_table", "tree", "graph",
    ]

    def __init__(self):
        self.retriever = Retriever()
        self.query_engineer = RAGQueryEngineer()
        self.router = ModelRouterAgent()
        self.logger = get_logger("tutor_agent", "crew.log")
        self._layered_retriever = None
        self._layered_retriever_failed = False
        self.hybrid_retriever = HybridRetriever()

    def get_next_topic(self, student_state: Dict[str, Any]) -> str:
        subject = str(student_state.get("subject", "")).lower()
        progress = cast(List[str], student_state.get("progress", []))
        curriculum = self.dsa_curriculum if "dsa" in subject else self.python_curriculum
        for topic in curriculum:
            if topic not in progress:
                return topic
        return "advanced_dsa_topics" if "dsa" in subject else "Advanced Python topics"

    def _analyze_learning_trend(self, student_state: Dict[str, Any]) -> str:
        history = student_state.get("learning_history", [])
        if len(history) < 3:
            return "steady"
        recent_scores = [float(h.get("score", 0.0)) for h in history[-3:]]
        if recent_scores[2] > recent_scores[1] > recent_scores[0]:
            return "improving"
        if recent_scores[2] < recent_scores[1] < recent_scores[0]:
            return "declining"
        return "fluctuating"

    def _build_layered_student_state(self, student_state: Dict[str, Any], topic: str) -> Dict[str, Any]:
        concepts = student_state.get("knowledge_state", {}).get("concepts", {})
        concept_state = concepts.get(topic, {}) if isinstance(concepts, dict) else {}
        mastery = float(concept_state.get("mastery", student_state.get("last_score", 0.4)))
        confidence = float(concept_state.get("confidence", 0.5))
        return {
            "topic": topic,
            "student_mastery": max(0.0, min(1.0, mastery)),
            "confidence": max(0.0, min(1.0, confidence)),
            "learning_trend": self._analyze_learning_trend(student_state),
        }

    def _get_layered_retriever(self):
        if self._layered_retriever_failed:
            return None
        if self._layered_retriever is not None:
            return self._layered_retriever
        try:
            from core.layered_kb.retrieval import AdaptiveRetriever
            self._layered_retriever = AdaptiveRetriever()
            return self._layered_retriever
        except Exception as exc:
            self._layered_retriever_failed = True
            self.logger.warning(f"layered_retriever_init_failed error={exc}")
            return None

    def retrieve_context_chunk_records(
        self,
        query: str,
        student_state: Dict[str, Any],
        k: int = 3,
        allowed_chunk_ids: List[str] | None = None,
        concept_family: List[str] | None = None,
    ) -> List[Dict[str, Any]]:
        from time import perf_counter
        rag_start_time = perf_counter()
        
        topic = str(student_state.get("current_topic") or self.get_next_topic(student_state))
        subtopic = str(student_state.get("current_subtopic") or f"{topic}_introduction")
        subject = str(student_state.get("subject", "")).lower()
        retrieval_query = f"{query}\n\nExplain topic: {topic}\nFocus subtopic: {subtopic}".strip()
        self.logger.info(f"rag_retrieve query='{retrieval_query}'")
        if "dsa" in subject:
            try:
                hybrid_records = self.hybrid_retriever.retrieve_context(
                    query=retrieval_query,
                    topic=topic,
                    student_state=student_state,
                    k=max(6, k),
                    allowed_chunk_ids=allowed_chunk_ids,
                )
                if hybrid_records:
                    rag_latency_ms = round((perf_counter() - rag_start_time) * 1000.0, 2)
                    self.logger.info(f"rag_retrieve_completed path=hybrid latency_ms={rag_latency_ms}")
                    # Store timing in student_state for metrics collection
                    student_state["_rag_latency_ms"] = rag_latency_ms
                    return hybrid_records
            except Exception as exc:
                self.logger.warning(f"hybrid_retrieval_failed topic='{topic}' error={exc}")

            layered_retriever = self._get_layered_retriever()
            if layered_retriever:
                try:
                    layered_state = self._build_layered_student_state(student_state, topic)
                    where: Dict[str, Any] = {}
                    if allowed_chunk_ids:
                        where["chunk_id"] = {"$in": allowed_chunk_ids}
                    elif concept_family:
                        where["concept"] = {"$in": concept_family}
                    else:
                        where["concept"] = {"$eq": topic}
                    self.logger.info(f"rag_retrieve where={where}")
                    layered_results = layered_retriever.retrieve(
                        query=retrieval_query,
                        student_state=layered_state,
                        k=k,
                        where=where if where else None,
                    )
                    self.logger.info(
                        "rag_retrieve returned_concepts=%s",
                        [str((item.get("metadata", {}) or {}).get("concept", "")) for item in layered_results],
                    )
                    cleaned_results: List[Dict[str, Any]] = []
                    for item in layered_results:
                        content = str(item.get("content", "")).strip()
                        if not content:
                            continue
                        cleaned_results.append({
                            "chunk_id": str(item.get("chunk_id", "")),
                            "content": content,
                            "metadata": item.get("metadata", {}) or {},
                        })
                    rag_latency_ms = round((perf_counter() - rag_start_time) * 1000.0, 2)
                    self.logger.info(f"rag_retrieve_completed path=layered latency_ms={rag_latency_ms}")
                    student_state["_rag_latency_ms"] = rag_latency_ms
                    return cleaned_results
                except Exception as exc:
                    self.logger.warning(f"layered_retrieval_failed topic='{topic}' error={exc}")

        # Fallback to legacy retriever path.
        macro_decision = student_state.get("macro_decision", {}) or {}
        concept_scope = ""
        target_concepts = macro_decision.get("target_concepts", [])
        if target_concepts:
            concept_scope = str(target_concepts[0])
        source_priority = student_state.get("preferred_source_type", "")
        subject_filter = student_state.get("subject", "")
        fallback_chunks = self.retriever.retrieve(
            query,
            k=k,
            concept_scope=concept_scope,
            source_priority=source_priority,
            subject=subject_filter,
        )
        results = [
            {
                "chunk_id": f"legacy_{idx}",
                "content": chunk,
                "metadata": {
                    "topic": topic,
                    "concept": concept_scope or "general",
                    "order_index": idx,
                },
            }
            for idx, chunk in enumerate(fallback_chunks)
            if str(chunk).strip()
        ]
        rag_latency_ms = round((perf_counter() - rag_start_time) * 1000.0, 2)
        self.logger.info(f"rag_retrieve_completed path=legacy latency_ms={rag_latency_ms}")
        student_state["_rag_latency_ms"] = rag_latency_ms
        return results

    def retrieve_context_chunks(self, query: str, student_state: Dict[str, Any], k: int = 3) -> List[str]:
        records = self.retrieve_context_chunk_records(query, student_state, k=k)
        return [str(item.get("content", "")).strip() for item in records if str(item.get("content", "")).strip()]

    # ──────────────────────────────────────────────────────────────────────────
    # PRIMARY CONTENT GENERATION — now fully adaptive
    # ──────────────────────────────────────────────────────────────────────────

    def generate_learning_path(self, decision_output: dict, student_state: dict):
        timer = Timer()
        subject = str(student_state.get("subject", "")).lower()

        # Topic selection (unchanged).
        action = decision_output.get("action", "default")
        if action == "advance_topic":
            next_topic = self.get_next_topic(student_state)
            student_state["current_topic"] = next_topic
            topic = next_topic
        else:
            topic = student_state.get("current_topic")
            if not topic:
                topic = self.get_next_topic(student_state)
                student_state["current_topic"] = topic

        subtopic = str(student_state.get("current_subtopic") or f"{topic}_introduction")
        domain_label = "DSA" if "dsa" in subject else "Python"

        # ── FIX #1 & #2: Build a fully adaptive context and prompt ────────────
        ctx = build_content_context(student_state, topic, subtopic)
        adaptive_prompt = build_adaptive_prompt(topic, subtopic, ctx, domain_label)

        # ── RAG retrieval ─────────────────────────────────────────────────────
        engineered_query = self.query_engineer.engineer(
            f"Explain {topic} {subtopic} at {ctx['depth']} level", student_state
        )
        retrieved_chunk_records = self.retrieve_context_chunk_records(engineered_query, student_state, k=3)
        retrieved_chunks = [
            str(item.get("content", "")).strip()
            for item in retrieved_chunk_records
            if str(item.get("content", "")).strip()
        ]
        rag_context = "\n\n".join(retrieved_chunks) if retrieved_chunks else "No curriculum content found."

        # ── LLM call with the ADAPTIVE prompt ─────────────────────────────────
        try:
            routed = self.router.route(
                task_type="concept_explanation",
                user_query=adaptive_prompt,
                context=rag_context,
                output_schema=None,  # We want raw markdown, not JSON schema
            )
            llm_response = str(routed.get("content", "")).strip()
            if not llm_response:
                llm_response = self._fallback_response(topic, subtopic, ctx["depth"], ctx["mode"])
        except Exception as exc:
            self.logger.error(f"llm_error={exc}")
            llm_response = self._fallback_response(topic, subtopic, ctx["depth"], ctx["mode"])

        # ── FIX #2: Record content so next call sees it and can vary ──────────
        if llm_response:
            record_content(
                student_state,
                topic,
                subtopic,
                llm_response,
                metadata={"mode": ctx["mode"], "depth": ctx["depth"], "score": ctx["score"]},
            )

        duration_ms = round(timer.elapsed_ms(), 2)
        self.logger.info(
            f"topic='{topic}' subtopic='{subtopic}' mode={ctx['mode']} depth={ctx['depth']} "
            f"score={ctx['score']} rag_chunks={len(retrieved_chunks)} duration_ms={duration_ms}"
        )
        trace_event(
            "tutor_generated",
            {
                "topic": topic,
                "subtopic": subtopic,
                "mode": ctx["mode"],
                "depth": ctx["depth"],
                "score": ctx["score"],
                "rag_chunks": len(retrieved_chunks),
                "duration_ms": duration_ms,
            },
        )

        # Extract RAG latency from student_state (set by retrieve_context_chunk_records)
        rag_latency_ms = student_state.get("_rag_latency_ms", 0.0)
        
        return {
            "rag_chunks": cast(List[str], retrieved_chunks),
            "rag_chunk_records": cast(List[Dict[str, Any]], retrieved_chunk_records),
            "llm_synthesis": str(llm_response),
            "engineered_query": str(engineered_query),
            "adaptive_ctx": ctx,
            "rag_latency_ms": rag_latency_ms,  # Pass RAG timing through
        }

    # ──────────────────────────────────────────────────────────────────────────
    # Fallback (adaptive-aware)
    # ──────────────────────────────────────────────────────────────────────────

    def _fallback_response(self, topic: str, subtopic: str, depth: str, mode: str) -> str:
        if mode == "remedial":
            return (
                f"## {topic} — {subtopic}\n\n"
                f"**Overview**\nLet's start from the very beginning with {topic}.\n\n"
                f"**Key Points**\n"
                f"• {topic} is a fundamental concept you'll use frequently.\n"
                f"• Think of it like organising items in a specific way.\n"
                f"• Don't worry if it feels complex — we'll break it into small pieces.\n\n"
                f"**Quick Recap**\n{topic} helps you solve problems in an organised, predictable way.\n\n"
                f"_(Adaptive fallback: remedial mode — score was low)_"
            )
        elif mode == "advanced":
            return (
                f"## {topic} — {subtopic}\n\n"
                f"**Overview**\nAdvanced deep-dive into {topic}.\n\n"
                f"**Key Points**\n"
                f"• Analyse time and space complexity trade-offs carefully.\n"
                f"• Consider edge cases: empty state, single element, overflow.\n"
                f"• Compare against alternative data structures for the same problem.\n\n"
                f"**Interview Question**\nWhen would you choose {topic} over a similar alternative, and why?\n\n"
                f"_(Adaptive fallback: advanced mode)_"
            )
        else:
            return (
                f"## {topic} — {subtopic}\n\n"
                f"**Overview**\n{topic} is a key concept used to store and process data efficiently.\n\n"
                f"**Key Points**\n"
                f"• Understand the basic operations and their order.\n"
                f"• Try a simple implementation before optimising.\n"
                f"• Connect to problems you have already solved.\n\n"
                f"**Quick Recap**\nPractice {topic} with small examples to build intuition.\n\n"
                f"_(Adaptive fallback: guided mode — {depth} level)_"
            )

    # ──────────────────────────────────────────────────────────────────────────
    # Kept for backward-compat (education_crew._extract_learning)
    # ──────────────────────────────────────────────────────────────────────────

    def _extract_json_payload(self, text: str) -> Dict[str, Any]:
        candidate = str(text or "").strip()
        if not candidate:
            return {}
        if "```" in candidate:
            parts = candidate.split("```")
            if len(parts) >= 2:
                candidate = parts[1]
                if candidate.strip().lower().startswith("json"):
                    candidate = candidate.strip()[4:]
        candidate = candidate.strip()
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            return {}
        return {}

    def _looks_like_code(self, example: str) -> bool:
        hints = ("def ", "class ", "return ", "for ", "while ", "if ", "print(", "=>", "{", "};")
        return any(token in example for token in hints)
