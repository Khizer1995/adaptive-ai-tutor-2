import random


class MonitorAgent:
    """
    Monitor Agent:
    - Simulates performance
    - Updates engagement
    - Tracks progress
    - Promotes level when appropriate
    """

    def interact(self, crew_output: dict, student_state: dict) -> dict:

        # ---------------------------
        # Simulate student score
        # ---------------------------
        new_score = round(random.uniform(0.5, 1.0), 2)
        student_state["last_score"] = new_score

        # ---------------------------
        # Update engagement
        # ---------------------------
        if new_score < 0.5:
            student_state["engagement"] = "low"
        elif new_score < 0.8:
            student_state["engagement"] = "medium"
        else:
            student_state["engagement"] = "high"

        # ---------------------------
        # Track topic properly
        # ---------------------------
        topic = student_state.get("current_topic")

        history = student_state.get("learning_history", [])
        history.append({
            "topic": topic,
            "score": new_score
        })
        student_state["learning_history"] = history

        # ---------------------------
        # Progress tracking
        # ---------------------------
        if new_score > 0.75:
            progress = student_state.get("progress", [])
            if topic and topic not in progress:
                progress.append(topic)
                student_state["progress"] = progress

        # ---------------------------
        # Level progression logic
        # ---------------------------
        if student_state["engagement"] == "high" and new_score > 0.85:
            if student_state["level"] == "beginner":
                student_state["level"] = "intermediate"
            elif student_state["level"] == "intermediate":
                student_state["level"] = "advanced"

        return {
            "delivered_by": "monitor_agent",
            "feedback": "Content delivered and student monitored.",
            "updated_student_state": student_state
        }
