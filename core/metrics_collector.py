from __future__ import annotations

from typing import Any, Dict, List

from core.logging_utils import log_jsonl


SUPPORT_ACTIONS = {"increase_support", "reinforce_basics"}
DECREASE_SUPPORT_ACTIONS = {"reduce_support"}
ADVANCE_ACTIONS = {"advance_topic", "challenge_with_variation", "increase_challenge"}


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return round(float(value), 4)
    except (TypeError, ValueError):
        return default


def _validation_checks(crew_output: Dict[str, Any]) -> Dict[str, bool]:
    existing = crew_output.get("validation_checks_passed")
    if isinstance(existing, dict):
        return {str(key): bool(value) for key, value in existing.items()}

    learning_path = str(crew_output.get("learning_path", "") or "").strip()
    status = str(crew_output.get("validation_status", "") or "").strip().lower()
    return {
        "has_learning_path": bool(learning_path),
        "validation_status_passed": status == "passed",
        "has_teacher_style": bool(str(crew_output.get("teacher_style", "") or "").strip()),
        "has_decision": isinstance(crew_output.get("decision", {}), dict),
    }


def _validation_score(checks: Dict[str, bool]) -> float:
    if not checks:
        return 0.0
    return round(sum(1 for passed in checks.values() if passed) / len(checks), 4)


def _scaffolding_direction(decision: Dict[str, Any], macro_decision: Dict[str, Any]) -> str:
    action = str(decision.get("action", "") or "")
    if action in SUPPORT_ACTIONS:
        return "increased_support"
    if action in DECREASE_SUPPORT_ACTIONS:
        return "decreased_support"
    if action in ADVANCE_ACTIONS:
        return "advanced"

    scaffold_policy = str(macro_decision.get("scaffold_policy", "") or "")
    if scaffold_policy == "high":
        return "increased_support"
    if scaffold_policy == "low":
        return "decreased_support"
    return "maintained"


def _source_types_from_records(rag_chunk_records: List[Dict[str, Any]]) -> List[str]:
    source_types = set()
    for record in rag_chunk_records:
        metadata = record.get("metadata", {}) or {}
        source = str(metadata.get("source", "") or "").lower()
        source_type = str(metadata.get("source_type", "") or "").lower()
        source_ref = str(metadata.get("source_ref", "") or "").lower()

        combined = " ".join([source, source_type, source_ref])
        if "pdf" in combined or source_type == "teacher_pdf":
            source_types.add("pdf")
        if "http://" in combined or "https://" in combined or "opendsa" in combined:
            source_types.add("url")
        if "cache" in combined or source == "merged":
            source_types.add("cached")

    return sorted(source_types)


def _latest_quiz_pass_rate(student_state: Dict[str, Any]) -> float:
    history = student_state.get("learning_history", []) or []
    for item in reversed(history):
        if isinstance(item, dict) and "score" in item:
            return _as_float(item.get("score"))
    return _as_float(student_state.get("last_score"))


def collect_learning_cycle_metrics(
    *,
    student_state: Dict[str, Any],
    macro_decision: Dict[str, Any],
    micro_decision: Dict[str, Any],
    crew_output: Dict[str, Any],
    timings: Dict[str, Any] | None = None,
    rag_chunk_records: List[Dict[str, Any]] | None = None,
    decision_iterations: int | None = None,
    quiz_pass_rate: float | None = None,
) -> Dict[str, Any]:
    checks = _validation_checks(crew_output)
    timings = timings or {}
    records = rag_chunk_records
    if records is None:
        records = crew_output.get("rag_chunk_records", []) or []

    return {
        "rag_latency_ms": _as_float(timings.get("rag_latency_ms")),
        "crewai_latency_ms": _as_float(timings.get("crewai_latency_ms")),
        "e2e_latency_ms": _as_float(timings.get("e2e_latency_ms")),
        "validation_score": (
            _as_float(crew_output.get("validation_score"))
            if "validation_score" in crew_output
            else _validation_score(checks)
        ),
        "validation_checks_passed": checks,
        "scaffolding_direction": _scaffolding_direction(micro_decision, macro_decision),
        "decision_iterations": int(
            decision_iterations
            if decision_iterations is not None
            else max(1, len(student_state.get("decision_trace", []) or []))
        ),
        "macro_decision": str(macro_decision.get("macro_action", "") or ""),
        "micro_decision": str(micro_decision.get("action", "") or ""),
        "source_types_used": _source_types_from_records(records),
        "quiz_pass_rate": _as_float(
            quiz_pass_rate if quiz_pass_rate is not None else _latest_quiz_pass_rate(student_state)
        ),
    }


def log_learning_cycle_metrics(**kwargs: Any) -> Dict[str, Any]:
    metrics = collect_learning_cycle_metrics(**kwargs)
    log_jsonl("metrics_log.jsonl", metrics)
    return metrics
