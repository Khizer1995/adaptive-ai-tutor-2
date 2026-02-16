class DecisionEngine:
    """
    Decision Engine

    Controls adaptive routing in LangGraph.
    Uses:
    - student performance
    - engagement level
    - learning trend (BONUS UPGRADE)
    """

    # ---------------------------------------------------
    # Learning Trend Analysis (BONUS UPGRADE)
    # ---------------------------------------------------

    def analyze_learning_trend(self, student_state: dict):

        history = student_state.get("learning_history", [])

        # Need at least 3 data points to detect trend
        if len(history) < 3:
            return "stable"

        scores = [h["score"] for h in history[-3:]]

        # Improving trend
        if scores[2] > scores[1] > scores[0]:
            return "improving"

        # Declining trend
        if scores[2] < scores[1] < scores[0]:
            return "declining"

        return "fluctuating"

    # ---------------------------------------------------
    # Main Decision Logic
    # ---------------------------------------------------

    def decide_next_step(self, student_state: dict) -> dict:
        """
        Decide which node in the LangGraph should execute next.
        """

        score = student_state.get("last_score", 0)
        engagement = student_state.get("engagement", "medium")

        # NEW: analyze learning trajectory
        trend = self.analyze_learning_trend(student_state)

        # ----------------------------------
        # Meta-adaptive rules (BONUS UPGRADE)
        # ----------------------------------

        # Improving fast → increase challenge
        if trend == "improving" and score > 0.6:
            return {
                "next_node": "education_crew",
                "action": "increase_challenge"
            }

        # Declining performance → reinforce basics
        if trend == "declining":
            return {
                "next_node": "education_crew",
                "action": "increase_support"
            }

        # ----------------------------------
        # Original adaptive rules
        # ----------------------------------

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

        # Default fallback
        return {
            "next_node": "education_crew",
            "action": "default_adjustment"
        }
