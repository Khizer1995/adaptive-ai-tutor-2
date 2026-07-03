"""
core/baseline_agent.py
=======================
No-Agent-System Baseline.

Purpose
-------
This module exists ONLY to produce a minimal, single-LLM-call baseline that
can be compared against the full multi-agent pipeline (LangGraph decision
engine + Education Crew + RAG retrieval + arbitration + validation + teacher
review), in order to test whether the multi-agent architecture is actually
doing real work.

By design, this module does NOT use:
  - LangGraph orchestration (core/langgraph_flow.py)
  - The Decision Engine (macro/micro decisions, arbitration)
  - RAG retrieval (hybrid / layered / legacy retrievers)
  - Multiple competing crew proposals
  - The Validation Agent
  - The Teacher Review Agent

It makes exactly ONE LLM call per scenario. The prompt is built directly from
the same fields present in the ablation fixtures (concept + student profile),
so both arms of the comparison see the same input information. The only
architectural difference under test is "one LLM call" vs "the full pipeline".
"""

from typing import Any, Dict

from core.llm.gemini_client import GeminiClient
from core.logging_utils import get_logger, trace_event, Timer


class NoAgentBaseline:
    """Minimal single-LLM-call tutor: one prompt in, one response out."""

    def __init__(self):
        self.client = GeminiClient()
        self.logger = get_logger("baseline_agent", "baseline.log")

    def _build_prompt(self, concept: str, student_profile: Dict[str, Any]) -> str:
        topic = student_profile.get("current_topic") or concept
        subtopic = student_profile.get("current_subtopic") or f"{concept}_introduction"
        level = student_profile.get("level", "beginner")
        engagement = student_profile.get("engagement", "medium")
        last_score = student_profile.get("last_score", 0.5)
        history = student_profile.get("learning_history", []) or []

        if history:
            history_lines = "\n".join(
                f"- {h.get('topic')} / {h.get('subtopic')}: score {h.get('score')}"
                for h in history
            )
        else:
            history_lines = "No prior learning history."

        return (
            "You are an AI tutor teaching Data Structures & Algorithms to a student.\n"
            "Generate one adaptive lesson in a single response. There is no other "
            "system support available to you beyond what is given below.\n\n"
            f"Student level: {level}\n"
            f"Engagement level: {engagement}\n"
            f"Most recent quiz score (0-1): {last_score}\n"
            f"Learning history:\n{history_lines}\n\n"
            f"Topic: {topic}\n"
            f"Subtopic: {subtopic}\n\n"
            "Write a short, clear lesson explaining this subtopic, adapted to the "
            "student's level and recent performance (e.g. simplify if the score is "
            "low, go deeper if the score is high). Structure the response with an "
            "Overview, Key Points, and a Quick Recap. Respond in Markdown."
        )

    def generate(self, scenario: Dict[str, Any]) -> Dict[str, Any]:
        """Run exactly one LLM call for a single fixture scenario."""
        timer = Timer()
        scenario_id = scenario.get("scenario_id", "")
        concept = scenario.get("concept", "")
        student_profile = scenario.get("student_profile", {}) or {}
        prompt = self._build_prompt(concept, student_profile)

        try:
            result = self.client.generate(prompt, task_type="baseline_single_call")
            content = str(result.get("content", "")).strip()
            provider_model = result.get("model")
        except Exception as exc:
            self.logger.error(f"baseline_llm_error scenario={scenario_id} error={exc}")
            content = ""
            provider_model = None

        latency_seconds = round(timer.elapsed_ms() / 1000.0, 4)

        self.logger.info(
            f"scenario={scenario_id} model={provider_model} "
            f"content_len={len(content)} latency_s={latency_seconds}"
        )
        trace_event(
            "baseline_generated",
            {
                "scenario_id": scenario_id,
                "model": provider_model,
                "latency_seconds": latency_seconds,
            },
        )

        return {
            "scenario_id": scenario_id,
            "concept": concept,
            "content": content,
            "model": provider_model,
            "latency_seconds": latency_seconds,
        }
