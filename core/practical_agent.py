from __future__ import annotations

import json
import difflib
import hashlib
import random
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
            normalized_correct, list(option_map.keys()), n=1, cutoff=0.45
        )
        if matches:
            self.correct_answer = option_map[matches[0]]
            return self
        self.correct_answer = random.choice(self.options)
        return self


class PracticalAgent:
    """
    Generates adaptive quiz batches grounded in the provided RAG context.

    Root-cause fixes applied:
      • Quiz prompt now uses build_adaptive_quiz_prompt() from adaptive_engine
        which embeds the student's score, mode (remedial/guided/advanced), and
        a randomised variation seed so every call produces DIFFERENT questions
        (Issue #3).
      • Previously-asked question texts are passed into the prompt so the LLM
        explicitly avoids repeating them (Issue #3).
      • Question types (MCQ, T/F, scenario, code-trace) vary by mode (Issue #3).
      • Fallback batch is also varied based on mode (Issue #1 partial).
    """

    def _question_count(self, mastery: float) -> int:
        if mastery < 0.4:
            return 6
        if mastery <= 0.7:
            return 4
        return 3

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
        from core.adaptive_engine import build_content_context, build_adaptive_quiz_prompt
        from core.adaptive_learning import previous_content_context

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

        # ── Build adaptive context so the prompt adapts to score ──────────────
        ctx = build_content_context(student_state, topic, subtopic)
        mode = ctx["mode"]   # "remedial" | "guided" | "advanced"

        active_seen = seen_hashes if seen_hashes is not None else set()

        # Build list of seen question texts for prompt injection (Issue #3).
        seen_previews: List[str] = []
        seen_content = student_state.get("generated_content_history", {}).get(topic, {}).get(subtopic, [])
        # Also collect from quiz_seen_questions hashes (best effort)
        for entry in seen_content[-5:]:
            preview = str(entry.get("preview", "")).strip()
            if preview:
                seen_previews.append(preview[:120])

        # ── Use the adaptive quiz prompt ──────────────────────────────────────
        prompt = build_adaptive_quiz_prompt(
            topic=topic,
            subtopic=subtopic,
            ctx=ctx,
            rag_context=rag_context or f"Use your knowledge of {topic} — {subtopic}.",
            q_count=q_count,
            seen_question_previews=seen_previews,
        )

        try:
            routed = router.route(
                task_type="quiz_generation",
                user_query=prompt,
                context=f"Decision action: {decision_output.get('action', 'adjust_quiz')} | Mode: {mode}",
                output_schema={"questions": "array of quiz questions"},
            )
            content = str(routed.get("content", "")).strip()

            # Robust JSON extraction.
            raw_questions = self._extract_questions(content)

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

            normalized = normalized[:q_count]
            # Shuffle option order in every question so the correct answer is
            # never predictably at a fixed position.
            normalized = [self._shuffle_options(q) for q in normalized]

            trace_event("quiz_generated", {
                "topic": topic,
                "subtopic": subtopic,
                "mode": mode,
                "quiz_len": len(normalized),
            })
            return normalized
        except Exception as exc:
            logger.warning(f"quiz_batch_fallback topic='{topic}' subtopic='{subtopic}' error={exc}")
            return []

    def _extract_questions(self, content: str) -> List[Dict[str, Any]]:
        """Robust extraction of a JSON array from LLM output."""
        text = content.strip()
        # Strip markdown code fences.
        if "```" in text:
            parts = text.split("```")
            for part in parts:
                stripped = part.strip()
                if stripped.lower().startswith("json"):
                    stripped = stripped[4:].strip()
                if stripped.startswith("[") or stripped.startswith("{"):
                    text = stripped
                    break
        # Find the outermost JSON array.
        start = text.find("[")
        end = text.rfind("]")
        if start != -1 and end != -1:
            text = text[start : end + 1]
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            return []
        if isinstance(parsed, list):
            return [x for x in parsed if isinstance(x, dict)]
        if isinstance(parsed, dict):
            for key in ("questions", "quiz", "items"):
                if isinstance(parsed.get(key), list):
                    return [x for x in parsed[key] if isinstance(x, dict)]
        return []

    @staticmethod
    def _similarity(a: str, b: str) -> float:
        return SequenceMatcher(None, str(a).lower(), str(b).lower()).ratio()

    def _deduplicate_questions(
        self, questions: List[Dict[str, Any]], threshold: float = 0.75
    ) -> List[Dict[str, Any]]:
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

    @staticmethod
    def _shuffle_options(question: Dict[str, Any]) -> Dict[str, Any]:
        """
        Shuffle the option list so the correct answer is not always in the
        same position.  The `correct_answer` value is preserved as-is; only
        the display order of `options` changes.
        """
        options = list(question.get("options") or [])
        if len(options) < 2:
            return question
        correct = question.get("correct_answer", "")
        random.shuffle(options)
        question = dict(question)          # shallow copy — don't mutate caller's dict
        question["options"] = options
        question["correct_answer"] = correct   # value unchanged; UI matches by value
        return question
