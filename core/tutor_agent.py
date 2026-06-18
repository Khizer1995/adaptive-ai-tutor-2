from core.rag.retriever import Retriever
from core.rag.query_engineering import RAGQueryEngineer
from core.llm.router import ModelRouterAgent
from core.learning_response_format import build_structured_explain_query
from core.logging_utils import get_logger, trace_event, Timer
from typing import Dict, Any, List, cast
import json
from core.hybrid_retriever import HybridRetriever

class TutorAgent:
    python_curriculum = [
        "Python variables",
        "Control flow (if/else)",
        "Loops",
        "Functions",
        "Lists and arrays",
        "Modules and packages",
        "Object-oriented programming",
        "Error handling",
        "File I/O"
    ]
    dsa_curriculum = [
        "array",
        "linked_list",
        "stack",
        "queue",
        "hash_table",
        "tree",
        "graph",
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
                        cleaned_results.append(
                            {
                                "chunk_id": str(item.get("chunk_id", "")),
                                "content": content,
                                "metadata": item.get("metadata", {}) or {},
                            }
                        )
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
        return [
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

    def retrieve_context_chunks(self, query: str, student_state: Dict[str, Any], k: int = 3) -> List[str]:
        records = self.retrieve_context_chunk_records(query, student_state, k=k)
        return [str(item.get("content", "")).strip() for item in records if str(item.get("content", "")).strip()]



    def generate_learning_path(self, decision_output: dict, student_state: dict):
        timer = Timer()
        level = student_state.get("level", "beginner")
        action = decision_output.get("action", "default")
        style = student_state.get("learning_style", "balanced")
        subject = str(student_state.get("subject", "")).lower()

        # Advance topic if action is 'advance_topic'
        if action == "advance_topic":
            next_topic = self.get_next_topic(student_state)
            student_state["current_topic"] = next_topic
            topic = next_topic
        else:
            topic = student_state.get("current_topic")
            if not topic:
                topic = self.get_next_topic(student_state)
                student_state["current_topic"] = topic

        # Adapt base_query based on learning style
        if style == "visual":
            base_query = f"Explain {topic} using diagrams and visual aids for {level} level. Include annotated code snippets."
        elif style == "problem-solver":
            base_query = f"Provide challenging problems and step-by-step solutions for {topic} at {level} level. Include minimal theory."
        elif action == "increase_support":
            base_query = f"Explain {topic} in simple terms for beginner with examples"
        elif level == "advanced":
            base_query = f"Provide deep technical explanation and edge cases for {topic}"
        else:
            base_query = f"Explain {topic} for {level} level student with examples"

        mastery = float(
            student_state.get("knowledge_state", {})
            .get("concepts", {})
            .get(topic, {})
            .get("mastery", student_state.get("last_score", 0.4))
        )
        show_complexity = mastery > 0.4
        structure_guard = (
            "Return markdown in this exact structure:\n"
            f"## {topic}\n\n"
            "1-2 sentence hook.\n\n"
            "### What is it?\n"
            "### How it works\n"
            "Use a numbered list.\n"
            "### Example\n"
            "Use one fenced code block.\n"
            "### Key Points\n"
            "Use 3 bullet points.\n"
            + ("### Time & Space Complexity\nUse a markdown table.\n" if show_complexity else "")
        )
        engineered_query = self.query_engineer.engineer(f"{base_query}\n\n{structure_guard}", student_state)
        retrieved_chunk_records = self.retrieve_context_chunk_records(engineered_query, student_state, k=3)
        retrieved_chunks = [
            str(item.get("content", "")).strip()
            for item in retrieved_chunk_records
            if str(item.get("content", "")).strip()
        ]
        context = "\n\n".join(retrieved_chunks) if retrieved_chunks else "No curriculum content found."
        domain_label = "DSA" if "dsa" in subject else "Python"

        try:
            routed = self.router.route(
                task_type="concept_explanation",
                user_query=build_structured_explain_query(topic, level, style, domain_label),
                context=context,
                output_schema={
                    "concept_overview": "1-2 lines",
                    "key_points": "3-5 concise bullets",
                    "operations_or_steps": "numbered if sequential",
                    "example": "minimal concrete example",
                    "common_mistakes": "2-3 bullets",
                    "quick_recap": "single line",
                },
            )
            llm_response = routed.get("content", "")
            llm_response = self._to_markdown_explanation(llm_response)
            if not llm_response:
                llm_response = self._fallback_response(topic, level, style)
        except Exception as exc:
            self.logger.error(f"llm_error={exc}")
            llm_response = self._fallback_response(topic, level, style)

        duration_ms = round(timer.elapsed_ms(), 2)
        self.logger.info(
            f"topic='{topic}' level={level} style={style} action={action} "
            f"rag_chunks={len(retrieved_chunks)} duration_ms={duration_ms}"
        )
        trace_event(
            "tutor_generated",
            {
                "topic": topic,
                "level": level,
                "style": style,
                "action": action,
                "rag_chunks": len(retrieved_chunks),
                "duration_ms": duration_ms,
            },
        )

        return {
            "rag_chunks": cast(List[str], retrieved_chunks),
            "rag_chunk_records": cast(List[Dict[str, Any]], retrieved_chunk_records),
            "llm_synthesis": str(llm_response),
            "engineered_query": str(engineered_query)
        }

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

    def _to_markdown_explanation(self, llm_response: str) -> str:
        payload = self._extract_json_payload(llm_response)
        if not payload:
            return str(llm_response or "").strip()

        lines: List[str] = []
        overview = str(payload.get("concept_overview", "")).strip()
        if overview:
            lines.append(overview)

        key_points = payload.get("key_points", [])
        if isinstance(key_points, list) and key_points:
            lines.append("")
            for item in key_points:
                value = str(item).strip()
                if value:
                    lines.append(f"• {value}")

        operations = payload.get("operations_or_steps", [])
        if isinstance(operations, list) and operations:
            lines.append("")
            step_num = 1
            for item in operations:
                value = str(item).strip()
                if value:
                    lines.append(f"{step_num}. {value}")
                    step_num += 1

        example = str(payload.get("example", "")).strip()
        if example:
            lines.append("")
            if self._looks_like_code(example):
                lines.append("```python")
                lines.append(example)
                lines.append("```")
            else:
                lines.append(example)

        return "\n".join(lines).strip()

    def _fallback_response(self, topic, level, style="balanced"):
        if style == "visual":
            return (
                f"[Visual Style]\n"
                f"- Diagram: [Imagine a diagram explaining {topic}]\n"
                f"- Annotated code: [Show code with comments for {topic}]\n"
                f"- Visual summary: [Key points in visual format]"
            )
        elif style == "problem-solver":
            return (
                f"[Problem-Solver Style]\n"
                f"- Challenge: Solve a real-world problem using {topic}.\n"
                f"- Step-by-step solution: [Detailed steps]"
            )
        # Balanced style fallback
        if level == "advanced":
            extra = "- Discuss edge cases and optimization\n- Consider performance implications"
        elif level == "intermediate":
            extra = "- Practice with multiple examples\n- Understand use cases"
        else:
            extra = "- Focus on basics\n- Try simple exercises"

        return f"""
Simple Explanation:
{topic} is a key concept in Python used to store and manipulate data.

Code Example:
x = 10
name = "Alice"
print(x, name)

Key Takeaways:
- Variables store data
- Python is dynamically typed
- No need to declare types
{extra}

(Level: {level} | Adaptive fallback mode)
"""
