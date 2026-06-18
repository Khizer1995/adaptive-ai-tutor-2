from __future__ import annotations

import json
import difflib
import hashlib
from typing import Any, Dict, List
from difflib import SequenceMatcher

from pydantic import BaseModel, Field, ValidationError, model_validator


def normalize_text(value: str) -> str:
    return " ".join(str(value or "").strip().lower().split())


class QuizQuestion(BaseModel):
    question: str
    options: List[str] = Field(min_length=4, max_length=4)
    correct_answer: str
    explanation: str

    @model_validator(mode="after")
    def validate_answer_in_options(self) -> "QuizQuestion":
        option_map = {normalize_text(opt): opt for opt in self.options}
        normalized_correct = normalize_text(self.correct_answer)
        if normalized_correct in option_map:
            self.correct_answer = option_map[normalized_correct]
            return self
        matches = difflib.get_close_matches(
            normalized_correct,
            list(option_map.keys()),
            n=1,
            cutoff=0.45,
        )
        if matches:
            self.correct_answer = option_map[matches[0]]
            return self
        self.correct_answer = self.options[0]
        return self


class PracticalAgent:
    """
    Generates adaptive quiz batches grounded in the provided RAG context.
    """

    def _question_count(self, mastery: float) -> int:
        if mastery < 0.4:
            return 6
        if mastery <= 0.7:
            return 4
        return 3

    def _fallback_question(self, topic: str, prompt: str, correct: str, wrong: List[str], explanation: str) -> Dict[str, Any]:
        return {
            "question": prompt,
            "options": [correct] + wrong[:3],
            "correct_answer": correct,
            "explanation": explanation,
        }

    def _fallback_batch(self, topic: str, count: int) -> List[Dict[str, Any]]:
        base = [
            self._fallback_question(
                topic,
                f"What is the core purpose of {topic}?",
                f"{topic.capitalize()} stores data to support predictable operations.",
                [
                    f"{topic.capitalize()} is only used in frontend styling.",
                    f"{topic.capitalize()} removes the need for algorithms.",
                    f"{topic.capitalize()} cannot be implemented in Python.",
                ],
                f"This is the best description of why {topic} exists.",
            ),
            self._fallback_question(
                topic,
                f"What usually happens when you perform a standard operation on {topic}?",
                "The operation follows the data structure's rules and updates its state.",
                [
                    "The operation always sorts all values automatically.",
                    "The operation has no effect on stored values.",
                    "The operation always throws an error.",
                ],
                "Correct operations follow defined behavior and modify or inspect state.",
            ),
            self._fallback_question(
                topic,
                f"Given code using {topic}, what should you do first to predict output?",
                "Track state changes step by step in operation order.",
                [
                    "Guess based on variable names only.",
                    "Assume every operation is O(n).",
                    "Ignore intermediate operations.",
                ],
                "Tracing requires following each operation in sequence.",
            ),
            self._fallback_question(
                topic,
                f"What edge case should be checked before removing an element from {topic}?",
                "Check whether the structure is empty.",
                [
                    "Check whether values are sorted.",
                    "Check whether there are duplicate values.",
                    "Check whether the structure is circular.",
                ],
                "Empty-structure checks prevent invalid operations.",
            ),
        ]
        return base[:count] if count <= len(base) else (base + [base[-1]] * (count - len(base)))

    def generate_quiz_batch(
        self,
        decision_output: Dict[str, Any],
        student_state: Dict[str, Any],
        rag_context: str,
        target_count: int | None = None,
        seen_hashes: set[str] | None = None,
    ) -> List[Dict[str, Any]]:
        from core.logging_utils import get_logger, trace_event
        from core.llm.router import ModelRouterAgent

        logger = get_logger("practical_agent", "crew.log")
        router = ModelRouterAgent()
        topic = str(student_state.get("current_topic", "topic"))
        subtopic = str(student_state.get("current_subtopic", f"{topic}_introduction"))
        mastery = float(
            student_state.get("knowledge_state", {})
            .get("concepts", {})
            .get(topic, {})
            .get("mastery", student_state.get("last_score", 0.4))
        )
        q_count = target_count if isinstance(target_count, int) and target_count > 0 else self._question_count(mastery)
        fallback = self._fallback_batch(topic, q_count)
        active_seen = seen_hashes if seen_hashes is not None else set()

        prompt = f"""
You are creating an adaptive MCQ batch for topic '{topic}' and subtopic '{subtopic}'.
Use ONLY the grounded RAG context below.

RAG context:
{rag_context}

Requirements:
- Generate exactly {q_count} MCQs.
- Every question must be COMPLETELY DIFFERENT from all others.
- Do not rephrase the same question.
- Cover different aspects: definition, purpose, operation, output tracing, edge case, comparison.
- If unique generation is impossible, return fewer questions instead of duplicates.
- Include at least:
  1 definitional question,
  2 application questions (or 1 if total questions = 3),
  1 tracing/output question,
  1 edge-case question.
- Return ONLY JSON array with objects:
  {{
    "question": "...",
    "options": ["A","B","C","D"],
    "correct_answer": "must be one of the 4 option texts",
    "explanation": "short why"
  }}
"""
        try:
            routed = router.route(
                task_type="quiz_generation",
                user_query=prompt,
                context=f"Decision action: {decision_output.get('action', 'adjust_quiz')}",
                output_schema={
                    "questions": "array of quiz questions",
                },
            )
            content = str(routed.get("content", "")).strip()
            payload = json.loads(content) if content.startswith("{") or content.startswith("[") else {}
            raw_questions = payload.get("questions", payload) if isinstance(payload, dict) else payload
            if not isinstance(raw_questions, list):
                raw_questions = []

            normalized: List[Dict[str, Any]] = []
            for item in raw_questions:
                try:
                    q = QuizQuestion.model_validate(item if isinstance(item, dict) else {})
                    normalized.append(q.model_dump())
                except ValidationError:
                    continue

            normalized = self._deduplicate_questions(normalized)
            if active_seen:
                normalized = self._filter_seen(normalized, active_seen)

            candidate_pool = normalized + fallback
            candidate_pool = self._deduplicate_questions(candidate_pool)
            if active_seen:
                candidate_pool = self._filter_seen(candidate_pool, active_seen)
            normalized = candidate_pool[:q_count]

            trace_event("quiz_generated", {"topic": topic, "subtopic": subtopic, "quiz_len": len(normalized)})
            return normalized
        except Exception as exc:
            logger.warning(f"quiz_batch_fallback topic='{topic}' subtopic='{subtopic}' error={exc}")
            filtered_fallback = self._deduplicate_questions(fallback)
            if active_seen:
                filtered_fallback = self._filter_seen(filtered_fallback, active_seen)
            return filtered_fallback[:q_count]
    @staticmethod
    def _similarity(a: str, b: str) -> float:
        return SequenceMatcher(None, str(a).lower(), str(b).lower()).ratio()

    def _deduplicate_questions(self, questions: List[Dict[str, Any]], threshold: float = 0.75) -> List[Dict[str, Any]]:
        unique: List[Dict[str, Any]] = []
        for candidate in questions:
            q_text = str(candidate.get("question", "")).strip()
            if not q_text:
                continue
            is_duplicate = any(
                self._similarity(q_text, str(seen.get("question", ""))) > threshold
                for seen in unique
            )
            if not is_duplicate:
                unique.append(candidate)
        return unique

    @staticmethod
    def _question_hash(q: str) -> str:
        return hashlib.md5(str(q).strip().lower().encode("utf-8")).hexdigest()

    def _filter_seen(
        self,
        questions: List[Dict[str, Any]],
        seen_hashes: set[str],
        threshold: float = 0.75,
    ) -> List[Dict[str, Any]]:
        fresh: List[Dict[str, Any]] = []
        for candidate in questions:
            q_text = str(candidate.get("question", "")).strip()
            if not q_text:
                continue
            q_hash = self._question_hash(q_text)
            if q_hash in seen_hashes:
                continue
            too_similar = any(
                self._similarity(q_text, str(existing.get("question", ""))) > threshold
                for existing in fresh
            )
            if too_similar:
                continue
            fresh.append(candidate)
            seen_hashes.add(q_hash)
        return fresh
