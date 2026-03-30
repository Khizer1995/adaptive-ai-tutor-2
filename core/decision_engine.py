class DecisionEngine:
    """
    Adaptive Decision Engine (Upgraded)

    Features:
    - Performance-based adaptation
    - Engagement-aware routing
    - Learning trend analysis
    - Continuous learning (no dead states)
    """

    def analyze_learning_trend(self, student_state: dict):
        history = student_state.get("learning_history", [])

        if len(history) < 3:
            return "stable"

        scores = [h["score"] for h in history[-3:]]

        if scores[2] > scores[1] > scores[0]:
            return "improving"

        if scores[2] < scores[1] < scores[0]:
            return "declining"

        return "fluctuating"

    def decide_next_step(self, student_state: dict) -> dict:
        score = student_state.get("last_score", 0)
        engagement = student_state.get("engagement", "medium")
        trend = self.analyze_learning_trend(student_state)

        # -------------------------------
        # 1. Critical states (priority)
        # -------------------------------

        if engagement == "low":
            return {
                "next_node": "education_crew",
                "action": "increase_support"
            }

        if trend == "declining":
            return {
                "next_node": "education_crew",
                "action": "reinforce_basics"
            }

        # -------------------------------
        # 2. Adaptive learning logic
        # -------------------------------

        # Weak performance
        if score < 0.5:
            return {
                "next_node": "education_crew",
                "action": "increase_support"
            }

        # Moderate performance
        if 0.5 <= score <= 0.75:
            if trend == "improving":
                return {
                    "next_node": "education_crew",
                    "action": "increase_challenge"
                }
            return {
                "next_node": "education_crew",
                "action": "adjust_quiz"
            }

        # -------------------------------
        # 3. High performance (IMPROVED)
        # -------------------------------

        if score > 0.75:
            if trend == "improving":
                return {
                    "next_node": "education_crew",   # ✅ KEEP LEARNING
                    "action": "advance_topic"
                }

            if trend == "fluctuating":
                return {
                    "next_node": "education_crew",
                    "action": "challenge_with_variation"
                }

            # Stable high → light monitoring
            return {
                "next_node": "monitor_agent",
                "action": "reduce_support"
            }

        # -------------------------------
        # Default fallback
        # -------------------------------

        return {
            "next_node": "education_crew",
            "action": "default_adjustment"
        }
        def decide_next_step(self, student_state: dict) -> dict:
            score = student_state.get("last_score", 0)
            engagement = student_state.get("engagement", "medium")
            trend = self.analyze_learning_trend(student_state)
            style = student_state.get("learning_style", "balanced")

            # --- Weighted adaptive reasoning ---
            actions = [
                "increase_support",
                "reinforce_basics",
                "adjust_quiz",
                "increase_challenge",
                "challenge_with_variation",
                "advance_topic",
                "reduce_support"
            ]
            weights = {a: 0 for a in actions}

            # Engagement-based weighting
            if engagement == "low":
                weights["increase_support"] += 3
                weights["reinforce_basics"] += 2
            elif engagement == "high":
                weights["increase_challenge"] += 2
                weights["advance_topic"] += 2

            # Trend-based weighting
            if trend == "declining":
                weights["reinforce_basics"] += 3
                weights["increase_support"] += 2
            elif trend == "improving":
                weights["advance_topic"] += 2
                weights["challenge_with_variation"] += 2

            # Score-based weighting
            if score < 0.5:
                weights["increase_support"] += 3
                weights["reinforce_basics"] += 2
            elif 0.5 <= score <= 0.75:
                weights["adjust_quiz"] += 2
                if trend == "improving":
                    weights["increase_challenge"] += 2
            elif score > 0.75:
                weights["advance_topic"] += 3
                if trend == "improving":
                    weights["challenge_with_variation"] += 2

            # Learning style influence (example: problem-solver prefers challenge)
            if style == "problem-solver":
                weights["increase_challenge"] += 1
                weights["challenge_with_variation"] += 1
            elif style == "visual":
                weights["adjust_quiz"] += 1

            # Select action with highest weight
            best_action = max(weights, key=lambda k: weights[k])

            return {
                "next_node": "education_crew",
                "action": best_action,
                "weights": weights,
                "reason": f"Selected '{best_action}' based on score={score}, engagement={engagement}, trend={trend}, style={style}"
            }