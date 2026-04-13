from core.rag.retriever import Retriever
from core.rag.query_engineering import RAGQueryEngineer
from core.llm.router import ModelRouterAgent
from core.logging_utils import get_logger, trace_event, Timer
from typing import Dict, Any, List, cast

class TutorAgent:
    curriculum = [
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

    def __init__(self):
        self.retriever = Retriever()
        self.query_engineer = RAGQueryEngineer()
        self.router = ModelRouterAgent()
        self.logger = get_logger("tutor_agent", "crew.log")

    def get_next_topic(self, student_state: Dict[str, Any]) -> str:
        progress = cast(List[str], student_state.get("progress", []))
        for topic in self.curriculum:
            if topic not in progress:
                return topic
        return "Advanced Python topics"



    def generate_learning_path(self, decision_output: dict, student_state: dict):
        timer = Timer()
        level = student_state.get("level", "beginner")
        action = decision_output.get("action", "default")
        style = student_state.get("learning_style", "balanced")
        macro_decision = student_state.get("macro_decision", {}) or {}

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

        engineered_query = self.query_engineer.engineer(base_query, student_state)
        concept_scope = ""
        target_concepts = macro_decision.get("target_concepts", [])
        if target_concepts:
            concept_scope = str(target_concepts[0])
        source_priority = student_state.get("preferred_source_type", "")
        subject = student_state.get("subject", "")
        retrieved_chunks = self.retriever.retrieve(
            engineered_query,
            k=3,
            concept_scope=concept_scope,
            source_priority=source_priority,
            subject=subject,
        )
        context = "\n\n".join(retrieved_chunks) if retrieved_chunks else "No curriculum content found."

        try:
            routed = self.router.route(
                task_type="concept_explanation",
                user_query=(
                    f"Explain topic '{topic}' for a {level} learner with learning style '{style}'. "
                    "Include misconception correction tips and examples."
                ),
                context=context,
                output_schema={
                    "simple_explanation": "2-4 short paragraphs",
                    "code_examples": "at least one Python code block",
                    "key_takeaways": "3 concise bullet points",
                },
            )
            llm_response = routed.get("content", "")
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
            "llm_synthesis": str(llm_response),
            "engineered_query": str(engineered_query)
        }

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
