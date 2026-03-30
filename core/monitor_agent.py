import random


class MonitorAgent:
    """
    Adaptive Monitor Agent (Upgraded)

    - Simulates realistic performance
    - Uses decision action to influence score
    - Updates engagement dynamically
    - Tracks progress + level progression
    """

    def interact(self, crew_output: dict, student_state: dict) -> dict:

        decision = crew_output.get("decision", {})
        action = decision.get("action", "default")

        prev_score = student_state.get("last_score", 0.5)

        # -----------------------------------
        # 1. Adaptive Score Simulation
        # -----------------------------------

        if action in ["increase_support", "reinforce_basics"]:
            # Support improves performance
            new_score = prev_score + random.uniform(0.05, 0.2)

        elif action in ["increase_challenge", "challenge_with_variation"]:
            # Challenge may reduce score slightly
            new_score = prev_score - random.uniform(0.0, 0.15)

        elif action == "advance_topic":
            # New topic → slight drop (learning curve)
            new_score = prev_score - random.uniform(0.05, 0.2)

        elif action == "adjust_quiz":
            # Stable performance
            new_score = prev_score + random.uniform(-0.05, 0.1)

        else:
            # Default randomness
            new_score = random.uniform(0.3, 0.9)

        # Clamp score between 0 and 1
        new_score = round(max(0.0, min(1.0, new_score)), 2)
        student_state["last_score"] = new_score

        # -----------------------------------
        # 2. Engagement Update (less rigid)
        # -----------------------------------

        if new_score < 0.4:
            student_state["engagement"] = "low"
        elif new_score < 0.75:
            student_state["engagement"] = "medium"
        else:
            student_state["engagement"] = "high"

        # -----------------------------------
        # 3. Learning History
        # -----------------------------------

        topic = student_state.get("current_topic")

        history = student_state.get("learning_history", [])
        history.append({
            "topic": topic,
            "score": new_score
        })
        student_state["learning_history"] = history

        # -----------------------------------
        # 4. Progress Tracking
        # -----------------------------------

        if new_score > 0.75:
            progress = student_state.get("progress", [])
            if topic and topic not in progress:
                progress.append(topic)
                student_state["progress"] = progress

        # -----------------------------------
        # 5. Level Progression (smarter)
        # -----------------------------------

        if new_score > 0.9 and student_state["engagement"] == "high":
            if student_state["level"] == "beginner":
                student_state["level"] = "intermediate"
            elif student_state["level"] == "intermediate":
                student_state["level"] = "advanced"

        # -----------------------------------
        # 6. Feedback (IMPROVED)
        # -----------------------------------

        if new_score < 0.5:
            feedback = "Student struggling — additional support recommended."
        elif new_score < 0.8:
            feedback = "Student progressing steadily."
        else:
            feedback = "Student performing strongly — ready for challenge."

        return {
            "delivered_by": "monitor_agent",
            "feedback": feedback,
            "updated_student_state": student_state
        }