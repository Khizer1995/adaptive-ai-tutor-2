from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any, Dict, List

from core.logging_utils import get_logger, log_jsonl, trace_event


HALLUCINATION_SIGNALS = ("i don't know", "as an ai", "i cannot")
GENERIC_SUBTOPIC_WORDS = {"intro", "introduction", "concept", "concepts", "basic", "basics"}


@dataclass
class ValidationResult:
    passed: bool
    checks: Dict[str, bool]
    score: float
    flags: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ValidationAgent:
    """
    Validates generated educational content before delivery.
    """

    def __init__(self) -> None:
        self.logger = get_logger("validation_agent", "validation.log")

    def validate_content(self, crew_output: dict, student_state: dict | None = None) -> dict:
        student_state = student_state or {}
        validated_output = crew_output.copy()

        topic = str(student_state.get("current_topic") or self._infer_topic(validated_output)).strip()
        subtopic = str(student_state.get("current_subtopic") or "").strip()
        subject = str(student_state.get("subject", "") or "").lower()
        learning_path = str(validated_output.get("learning_path", "") or "")
        quiz = validated_output.get("quiz", []) or []

        checks = {
            "length": self._word_count(learning_path) > 100,
            "topic_relevance": self._topic_relevance_passed(learning_path, topic, subtopic),
            "code_presence": self._code_presence_passed(learning_path, subject, topic),
            "hallucination_signals": not self._hallucination_flags(learning_path),
            "quiz_alignment": self._quiz_alignment_passed(quiz, topic, subtopic),
            "adaptive_level_alignment": self._adaptive_level_alignment_passed(learning_path, student_state),
        }
        flags = self._build_flags(checks, learning_path, student_state)
        score = round(sum(1 for passed in checks.values() if passed) / len(checks), 4)
        result = ValidationResult(
            passed=all(checks.values()),
            checks=checks,
            score=score,
            flags=flags,
        )

        validated_output["validation_result"] = result.to_dict()
        validated_output["validation_status"] = "passed" if result.passed else "failed"
        validated_output["validation_score"] = result.score
        validated_output["validation_checks_passed"] = result.checks
        validated_output["validation_flags"] = result.flags
        validated_output["adaptive_delivery_level"] = self._expected_delivery_level(student_state)

        log_jsonl(
            "validation_log.jsonl",
            {
                "student_id": student_state.get("student_id"),
                "topic": topic,
                "subtopic": subtopic,
                "validation_result": result.to_dict(),
                "adaptive_delivery_level": validated_output["adaptive_delivery_level"],
            },
        )
        self.logger.info(
            f"validation_status={validated_output.get('validation_status')} "
            f"score={result.score} flags={result.flags}"
        )
        trace_event(
            "validation_completed",
            {
                "status": validated_output.get("validation_status"),
                "score": result.score,
                "flags": result.flags,
            },
        )
        return validated_output

    @staticmethod
    def _word_count(text: str) -> int:
        return len(re.findall(r"\b\w+\b", text or ""))

    @staticmethod
    def _keywords(topic: str, subtopic: str) -> List[str]:
        raw = f"{topic} {subtopic}".replace("-", "_")
        tokens = re.findall(r"[a-zA-Z0-9]+", raw.lower())
        keywords: List[str] = []
        for token in tokens:
            if len(token) < 3 or token in GENERIC_SUBTOPIC_WORDS:
                continue
            if token not in keywords:
                keywords.append(token)
        return keywords

    def _topic_relevance_passed(self, text: str, topic: str, subtopic: str) -> bool:
        lowered = text.lower()
        matches = [keyword for keyword in self._keywords(topic, subtopic) if keyword in lowered]
        return len(matches) >= 2

    @staticmethod
    def _is_dsa_topic(subject: str, topic: str) -> bool:
        dsa_topics = {
            "array",
            "linked_list",
            "linked list",
            "stack",
            "queue",
            "hash_table",
            "hash table",
            "tree",
            "graph",
            "sorting",
            "binary_search",
            "binary search",
        }
        normalized_topic = topic.strip().lower().replace("_", " ")
        return "dsa" in subject or normalized_topic in dsa_topics

    def _code_presence_passed(self, text: str, subject: str, topic: str) -> bool:
        if not self._is_dsa_topic(subject, topic):
            return True
        return "```" in text

    @staticmethod
    def _hallucination_flags(text: str) -> List[str]:
        lowered = text.lower()
        return [signal for signal in HALLUCINATION_SIGNALS if signal in lowered]

    def _quiz_alignment_passed(self, quiz: Any, topic: str, subtopic: str) -> bool:
        if not isinstance(quiz, list) or not quiz:
            return False

        subtopic_keywords = [
            keyword
            for keyword in self._keywords("", subtopic)
            if keyword not in set(self._keywords(topic, ""))
        ]
        keywords = subtopic_keywords or self._keywords(topic, subtopic)
        if not keywords:
            return False

        aligned = 0
        for item in quiz:
            question = item.get("question", "") if isinstance(item, dict) else str(item)
            lowered = question.lower()
            if any(keyword in lowered for keyword in keywords):
                aligned += 1
        return aligned == len(quiz)

    @staticmethod
    def _expected_delivery_level(student_state: Dict[str, Any]) -> str:
        score = float(student_state.get("last_score", 0.0) or 0.0)
        if score < 0.45:
            return "simplified"
        if score >= 0.75:
            return "advanced"
        return "standard"

    def _adaptive_level_alignment_passed(self, text: str, student_state: Dict[str, Any]) -> bool:
        expected = self._expected_delivery_level(student_state)
        lowered = text.lower()
        if expected == "simplified":
            return any(marker in lowered for marker in ("simple", "step by step", "beginner", "basics", "analogy"))
        if expected == "advanced":
            return any(marker in lowered for marker in ("complexity", "edge case", "implementation", "advanced"))
        return True

    def _build_flags(self, checks: Dict[str, bool], text: str, student_state: Dict[str, Any]) -> List[str]:
        flags = [name for name, passed in checks.items() if not passed]
        flags.extend(f"hallucination_signal:{signal}" for signal in self._hallucination_flags(text))

        expected = self._expected_delivery_level(student_state)
        if expected == "simplified" and not checks.get("adaptive_level_alignment", False):
            flags.append("content_should_be_simplified_for_low_score")
        elif expected == "advanced" and not checks.get("adaptive_level_alignment", False):
            flags.append("content_should_match_higher_student_standard")
        return sorted(set(flags))

    @staticmethod
    def _infer_topic(crew_output: Dict[str, Any]) -> str:
        decision = crew_output.get("decision", {}) or {}
        return str(decision.get("topic") or crew_output.get("topic") or "")
