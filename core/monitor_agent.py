import random

class MonitorAgent:

    def interact(self, crew_output: dict, student_state: dict) -> dict:
        updated_state = student_state.copy()

        current_score = updated_state.get("last_score", 0.5)

        # Simulate learning improvement
        improvement = random.uniform(0.05, 0.15)
        new_score = min(current_score + improvement, 1.0)

        updated_state["last_score"] = round(new_score, 2)

        # Engagement slightly fluctuates
        if new_score > 0.75:
            updated_state["engagement"] = "high"
        elif new_score < 0.4:
            updated_state["engagement"] = "low"
        else:
            updated_state["engagement"] = "medium"

        return {
            "delivered_by": crew_output.get("agent"),
            "feedback": "Content delivered and student monitored.",
            "updated_student_state": updated_state
        }
