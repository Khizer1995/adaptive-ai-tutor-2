class DecisionEngine:
    def decide_next_step(self, student_state: dict) -> dict:
        """
        Decide which node in the LangGraph should execute next.
        """

        score = student_state.get("last_score", 0)
        engagement = student_state.get("engagement", "medium")

        # Low engagement → more support
        if engagement == "low":
            return {
                "next_node": "education_crew",
                "action": "increase_support"
            }

        # Low score → scaffold more
        if score < 0.5:
            return {
                "next_node": "education_crew",
                "action": "adjust_learning_path"
            }

        # Medium score → practical reinforcement
        if 0.5 <= score <= 0.75:
            return {
                "next_node": "education_crew",
                "action": "adjust_quiz"
            }

        # High score → reduce support
        if score > 0.75:
            return {
                "next_node": "monitor_agent",
                "action": "reduce_support"
            }

        return {
            "next_node": "education_crew",
            "action": "default_adjustment"
        }
