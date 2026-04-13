"""
RAG Query Engineering utilities.
- Refines and expands queries for better retrieval.
- Can add context, synonyms, or rephrase for LLMs.
"""
from typing import Dict
from core.logging_utils import get_logger, trace_event

class RAGQueryEngineer:
    def __init__(self):
        self.logger = get_logger("rag_query", "rag.log")

    def engineer(self, query: str, student_state: Dict = None) -> str:
        """
        Improve the query for retrieval and LLM synthesis.
        - Add synonyms, context, or rephrase for clarity.
        - Optionally use student_state for personalization.
        """
        # Example: Add synonyms and context
        base = query
        if student_state:
            level = student_state.get("level", "beginner")
            base += f" [difficulty: {level}]"
            if student_state.get("engagement") == "low":
                base += " [make it more engaging]"
            macro_decision = student_state.get("macro_decision", {}) or {}
            concept_scope = macro_decision.get("target_concepts", [])
            scaffold_policy = macro_decision.get("scaffold_policy")
            if concept_scope:
                cleaned_scope = [str(item).strip() for item in concept_scope if item is not None and str(item).strip()]
                if cleaned_scope:
                    base += f" [concept_scope: {', '.join(cleaned_scope)}]"
            if scaffold_policy:
                base += f" [scaffold: {scaffold_policy}]"
        # Add more engineering logic as needed
        self.logger.info(f"engineered_query_len={len(base)}")
        trace_event("rag_query_engineered", {"length": len(base)})
        return base
