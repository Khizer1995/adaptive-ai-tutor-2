from typing import Any, Dict, Optional

from core.logging_utils import get_logger, trace_event
from core.llm.gemini_client import GeminiClient
from core.llm.groq_client import GroqClient


class ModelRouterAgent:
    """
    Routes LLM tasks between Gemini and Groq.

    Input:
    - task_type
    - user_query
    - context (optional)
    - output_schema (optional)
    """

    GEMINI_TASKS = {
        "deep_reasoning",
        "concept_explanation",
        "misconception_correction",
    }

    GROQ_TASKS = {
        "quiz_generation",
        "fast_response",
        "basic_evaluation",
    }

    def __init__(self):
        self.logger = get_logger("model_router", "crew.log")
        self.gemini_client = None
        self.groq_client = None

    def route(
        self,
        task_type: str,
        user_query: str,
        context: Optional[str] = None,
        output_schema: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        provider = self._select_provider(task_type)
        prompt = self._build_prompt(task_type, user_query, context, output_schema)

        try:
            if provider == "gemini":
                result = self._get_gemini_client().generate(prompt, task_type)
            else:
                result = self._get_groq_client().generate(prompt, task_type)
            selected_provider = provider
        except Exception as exc:
            # Explicit fallback rule: Gemini -> Groq
            if provider == "gemini":
                self.logger.warning(f"gemini_failed_fallback_to_groq error={exc}")
                result = self._get_groq_client().generate(prompt, task_type)
                selected_provider = "groq_fallback"
            else:
                raise

        normalized = {
            "task_type": task_type,
            "selected_provider": selected_provider,
            "content": result.get("content", "").strip(),
            "provider_metadata": {
                "provider": result.get("provider"),
                "model": result.get("model"),
            },
        }
        self.logger.info(
            f"task_type={task_type} selected_provider={selected_provider} "
            f"content_len={len(normalized['content'])}"
        )
        trace_event(
            "model_routed",
            {
                "task_type": task_type,
                "selected_provider": selected_provider,
                "provider": result.get("provider"),
                "model": result.get("model"),
            },
        )
        return normalized

    def _select_provider(self, task_type: str) -> str:
        if task_type in self.GEMINI_TASKS:
            return "gemini"
        if task_type in self.GROQ_TASKS:
            return "groq"
        # Safe default to Groq for unknown tasks to preserve Gemini quota.
        return "groq"

    def _build_prompt(
        self,
        task_type: str,
        user_query: str,
        context: Optional[str],
        output_schema: Optional[Dict[str, str]],
    ) -> str:
        schema_text = ""
        if output_schema:
            lines = [f'- "{key}": {description}' for key, description in output_schema.items()]
            schema_text = "Expected JSON fields:\n" + "\n".join(lines)

        context_text = context or "No additional context provided."
        return (
            "You are part of a Cognitive Adaptive AI Tutor system.\n"
            f"Task Type: {task_type}\n"
            "Instruction: Answer accurately using the context when relevant.\n"
            "Response Rules:\n"
            "- Be concise and pedagogically clear.\n"
            "- If context is insufficient, explicitly say so.\n"
            "- Prefer structured output.\n\n"
            f"User Query:\n{user_query}\n\n"
            f"Context:\n{context_text}\n\n"
            f"{schema_text}"
        )

    def _get_gemini_client(self) -> GeminiClient:
        if self.gemini_client is None:
            self.gemini_client = GeminiClient()
        return self.gemini_client

    def _get_groq_client(self) -> GroqClient:
        if self.groq_client is None:
            self.groq_client = GroqClient()
        return self.groq_client
