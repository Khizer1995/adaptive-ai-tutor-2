from core.logging_utils import get_logger, trace_event, Timer


class MonitorAgent:
    """
    Execution monitor.

    This agent records interaction outcomes only.
    It does not make pedagogical routing or adaptation decisions,
    and it must not mutate quiz-derived scores.
    """

    def interact(self, crew_output: dict, student_state: dict) -> dict:
        timer = Timer()
        logger = get_logger("monitor_agent", "monitor.log")

        current_score = round(max(0.0, min(1.0, float(student_state.get("last_score", 0.5)))), 2)
        selected_owner = crew_output.get("owner_agent", "unknown")
        challenge_level = crew_output.get("challenge_level", "medium")

        if current_score < 0.4:
            student_state["engagement"] = "low"
        elif current_score < 0.75:
            student_state["engagement"] = "medium"
        else:
            student_state["engagement"] = "high"

        topic = student_state.get("current_topic")

        if current_score < 0.5:
            feedback = "Observed low performance in this interaction."
        elif current_score < 0.8:
            feedback = "Observed steady performance in this interaction."
        else:
            feedback = "Observed strong performance in this interaction."

        duration_ms = round(timer.elapsed_ms(), 2)
        logger.info(
            f"owner={selected_owner} challenge={challenge_level} score={current_score} "
            f"engagement={student_state.get('engagement')} topic='{topic}' duration_ms={duration_ms}"
        )
        trace_event(
            "monitor_update",
            {
                "owner": selected_owner,
                "challenge_level": challenge_level,
                "score": current_score,
                "engagement": student_state.get("engagement"),
                "topic": topic,
                "duration_ms": duration_ms,
            },
        )

        return {
            "delivered_by": "monitor_agent",
            "feedback": feedback,
            "execution_feedback": {
                "topic": topic,
                "observed_score": current_score,
                "observed_engagement": student_state.get("engagement"),
                "selected_owner": selected_owner,
                "challenge_level": challenge_level,
            },
            "updated_student_state": student_state,
        }
