import re
from typing import Any, Dict, List, Optional

from core.logging_utils import log_learning_record


_SECTION_HEADERS = [
    "Simple Explanation",
    "Code Example",
    "Key Takeaways",
]


def _extract_section(text: str, header: str) -> Optional[str]:
    if not text:
        return None
    pattern = rf"{re.escape(header)}\\s*:\\s*(.*?)(?:(?:\\n\\s*(?:{'|'.join(map(re.escape, _SECTION_HEADERS))})\\s*:)|\\Z)"
    match = re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return None
    content = match.group(1).strip()
    return content or None


def _extract_key_takeaways(text: str) -> List[str]:
    section = _extract_section(text, "Key Takeaways")
    if not section:
        return []
    lines = [line.strip() for line in section.splitlines()]
    items = []
    for line in lines:
        if not line:
            continue
        if line.startswith(("-", "*")):
            items.append(line[1:].strip())
        else:
            items.append(line)
    return items


def build_learning_record(state: Dict[str, Any]) -> Dict[str, Any]:
    student_state = state.get("student_state", {}) or {}
    crew_output = state.get("crew_output", {}) or {}
    decision = crew_output.get("decision") or state.get("decision", {}) or {}
    review = state.get("teacher_review", {}) or {}

    learning_path = crew_output.get("learning_path") or ""
    if not isinstance(learning_path, str):
        learning_path = str(learning_path)

    record = {
        "student_id": student_state.get("student_id"),
        "student_name": student_state.get("name"),
        "level": student_state.get("level"),
        "engagement": student_state.get("engagement"),
        "current_topic": student_state.get("current_topic"),
        "decision": {
            "action": decision.get("action"),
            "next_node": decision.get("next_node"),
            "reason": decision.get("reason"),
        },
        "teacher_style": crew_output.get("teacher_style"),
        "validation_status": crew_output.get("validation_status"),
        "review_status": review.get("review_status"),
        "learning_path": learning_path,
        "quiz": crew_output.get("quiz", []),
        "rag_chunks": crew_output.get("rag_chunks", []),
        "engineered_query": crew_output.get("engineered_query", ""),
        "code_example": _extract_section(learning_path, "Code Example"),
        "key_takeaways": _extract_key_takeaways(learning_path),
    }
    return record


def log_state_learning_record(state: Dict[str, Any]) -> None:
    record = build_learning_record(state)
    log_learning_record(record)
