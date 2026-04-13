import random
from core.logging_utils import get_logger, trace_event, Timer


class MonitorAgent:
    """
    Execution monitor.

    This agent records interaction outcomes only.
    It does not make pedagogical routing or adaptation decisions.
    """

    def interact(self, crew_output: dict, student_state: dict) -> dict:
        timer = Timer()
        logger = get_logger("monitor_agent", "monitor.log")

        prev_score = student_state.get("last_score", 0.5)
        selected_owner = crew_output.get("owner_agent", "unknown")
        challenge_level = crew_output.get("challenge_level", "medium")

        if challenge_level == "low":
            new_score = prev_score + random.uniform(0.05, 0.2)
        elif challenge_level == "high":
            new_score = prev_score - random.uniform(0.0, 0.15)
        else:
            new_score = prev_score + random.uniform(-0.05, 0.1)

        new_score = round(max(0.0, min(1.0, new_score)), 2)
        student_state["last_score"] = new_score

        if new_score < 0.4:
            student_state["engagement"] = "low"
        elif new_score < 0.75:
            student_state["engagement"] = "medium"
        else:
            student_state["engagement"] = "high"

        topic = student_state.get("current_topic")
        history = student_state.get("learning_history", [])
        history.append({"topic": topic, "score": new_score})
        student_state["learning_history"] = history

        if new_score < 0.5:
            feedback = "Observed low performance in this interaction."
        elif new_score < 0.8:
            feedback = "Observed steady performance in this interaction."
        else:
            feedback = "Observed strong performance in this interaction."

        duration_ms = round(timer.elapsed_ms(), 2)
        logger.info(
            f"owner={selected_owner} challenge={challenge_level} score={new_score} "
            f"engagement={student_state.get('engagement')} topic='{topic}' duration_ms={duration_ms}"
        )
        trace_event(
            "monitor_update",
            {
                "owner": selected_owner,
                "challenge_level": challenge_level,
                "score": new_score,
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
                "observed_score": new_score,
                "observed_engagement": student_state.get("engagement"),
                "selected_owner": selected_owner,
                "challenge_level": challenge_level,
            },
            "updated_student_state": student_state,
        }
