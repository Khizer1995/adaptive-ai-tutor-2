import random


class MonitorAgent:
    """
    Monitor Agent

    Responsibilities:
    - Simulate student interaction feedback
    - Update engagement and performance
    - Maintain learning memory (history of topics + scores)
    """

    def interact(self, crew_output: dict, student_state: dict) -> dict:
        """
        Receives educational output and updates student state.
        """

        # ----------------------------------
        # Simulate student performance
        # ----------------------------------

        # Random score simulation (you can replace later)
        new_score = round(random.uniform(0.5, 1.0), 2)

        student_state["last_score"] = new_score

        # Update engagement based on score
        if new_score < 0.5:
            student_state["engagement"] = "low"
        elif new_score < 0.8:
            student_state["engagement"] = "medium"
        else:
            student_state["engagement"] = "high"

        # ----------------------------------
        # Learning Memory Tracking (FINAL UPGRADE)
        # ----------------------------------

        topic = None

        if "learning_path" in crew_output and crew_output["learning_path"]:
            first_step = crew_output["learning_path"][0]

            # Extract topic safely
            if "of " in first_step:
                topic = first_step.split("of ", 1)[1]
            else:
                topic = first_step

        history = student_state.get("learning_history", [])

        history.append({
            "topic": topic,
            "score": new_score
        })

        student_state["learning_history"] = history

        # ----------------------------------
        # Return result
        # ----------------------------------

        return {
            "delivered_by": "monitor_agent",
            "feedback": "Content delivered and student monitored.",
            "updated_student_state": student_state
        }
