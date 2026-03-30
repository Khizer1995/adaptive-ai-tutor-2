from typing import Dict, Any

from core.logging_utils import get_logger, log_jsonl


def evaluate_cycle(
    student_state: Dict[str, Any],
    decision: Dict[str, Any],
    crew_output: Dict[str, Any],
    timings: Dict[str, float],
) -> Dict[str, Any]:
    """
    Map system signals to evaluation criteria inspired by AIA-PAL.
    This is lightweight and traceable for report generation.
    """
    logger = get_logger("evaluation", "evaluation.log")

    last_score = student_state.get("last_score", 0)
    action = decision.get("action", "unknown")
    validation_status = crew_output.get("validation_status", "unknown")

    evaluation = {
        "accuracy": last_score,
        "adaptability": action,
        "response_time_ms": timings,
        "workflow_coordination": "ok" if validation_status == "passed" else "check",
        "tracking_agents": "ok" if student_state.get("learning_history") else "check",
        "errors_inconsistencies": [] if validation_status == "passed" else ["validation_failed"],
        "expert_review": validation_status,
        "scaffolding_strategies": action in [
            "increase_support",
            "reinforce_basics",
            "reduce_support",
        ],
    }

    logger.info(
        f"accuracy={last_score} action={action} validation={validation_status} "
        f"timings={timings}"
    )
    log_jsonl("evaluation.jsonl", evaluation)
    return evaluation
