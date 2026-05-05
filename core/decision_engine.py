from core.logging_utils import get_logger, trace_event


class DecisionEngine:
    """
    Adaptive Decision Engine

    Features:
    - Performance-based adaptation
    - Engagement-aware routing
    - Learning trend analysis
    - Weighted decision-making
    """

    def __init__(self):
        self.logger = get_logger("decision_engine", "decision_engine.log")

    def _knowledge_snapshot(self, student_state: dict) -> tuple[float, float, str]:
        knowledge_state = student_state.get("knowledge_state", {}) or {}
        concepts = knowledge_state.get("concepts", {}) or {}
        if not concepts:
            topic = student_state.get("current_topic") or "general"
            return 0.0, 0.0, topic
        concept_items = list(concepts.items())
        avg_mastery = sum(v.get("mastery", 0.0) for _, v in concept_items) / len(concept_items)
        avg_confidence = sum(v.get("confidence", 0.0) for _, v in concept_items) / len(concept_items)
        weakest_concept = min(concept_items, key=lambda item: item[1].get("mastery", 0.0))[0]
        return avg_mastery, avg_confidence, weakest_concept

    def decide_macro_plan(self, student_state: dict) -> dict:
        score = student_state.get("last_score", 0.0)
        engagement = student_state.get("engagement", "medium")
        trend = self.analyze_learning_trend(student_state)
        avg_mastery, avg_confidence, weakest_concept = self._knowledge_snapshot(student_state)

        if score < 0.45 or trend == "declining":
            macro_action = "stabilize_foundations"
            scaffold_policy = "high"
        elif avg_mastery > 0.75 and avg_confidence > 0.7:
            macro_action = "advance_concepts"
            scaffold_policy = "low"
        else:
            macro_action = "guided_progression"
            scaffold_policy = "medium"

        if engagement == "low" and scaffold_policy != "high":
            scaffold_policy = "medium"

        macro_plan = {
            "macro_action": macro_action,
            "target_concepts": [weakest_concept],
            "scaffold_policy": scaffold_policy,
            "reason": (
                f"macro_action={macro_action} based on score={score}, trend={trend}, "
                f"avg_mastery={round(avg_mastery, 2)}, avg_confidence={round(avg_confidence, 2)}"
            ),
        }
        trace_event("macro_decision_made", macro_plan)
        return macro_plan

    def analyze_learning_trend(self, student_state: dict) -> str:
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
        style = student_state.get("learning_style", "balanced")
        macro_plan = student_state.get("macro_decision", {}) or {}
        macro_action = macro_plan.get("macro_action", "")
        scaffold_policy = macro_plan.get("scaffold_policy", "medium")

        actions = [
            "increase_support",
            "reinforce_basics",
            "adjust_quiz",
            "increase_challenge",
            "challenge_with_variation",
            "advance_topic",
            "reduce_support",
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

        # Score-based weighting (updated thresholds)
        if score < 0.4:
            weights["increase_support"] += 3
            weights["reinforce_basics"] += 2
        elif 0.4 <= score < 0.65:
            weights["adjust_quiz"] += 2
            if trend == "improving":
                weights["increase_challenge"] += 1
        else:
            # score >= 0.65
            if engagement in ("medium", "high"):
                weights["advance_topic"] += 4
            else:
                weights["adjust_quiz"] += 2
            if trend == "improving":
                weights["challenge_with_variation"] += 2
            else:
                weights["reduce_support"] += 1

        # Learning style influence (problem-solver prefers challenge)
        if style == "problem-solver":
            weights["increase_challenge"] += 1
            weights["challenge_with_variation"] += 1
        elif style == "visual":
            weights["adjust_quiz"] += 1

        # Macro policy nudges micro action without replacing baseline behavior.
        if scaffold_policy == "high":
            weights["increase_support"] += 2
            weights["reinforce_basics"] += 1
        elif scaffold_policy == "low":
            weights["advance_topic"] += 1
            weights["increase_challenge"] += 1

        best_action = max(weights, key=lambda k: weights[k])
        if macro_action == "advance_concepts" and student_state.get("current_subtopic"):
            best_action = "advance_topic"
        next_node = "education_crew"
        if best_action == "reduce_support":
            next_node = "monitor_agent"

        decision = {
            "next_node": next_node,
            "action": best_action,
            "weights": weights,
            "reason": (
                f"Selected '{best_action}' based on score={score}, "
                f"engagement={engagement}, trend={trend}, style={style}"
            ),
        }

        self.logger.info(
            f"score={score} engagement={engagement} trend={trend} "
            f"style={style} action={best_action} next_node={next_node}"
        )
        trace_event(
            "decision_made",
            {
                "score": score,
                "engagement": engagement,
                "trend": trend,
                "style": style,
                "action": best_action,
                "next_node": next_node,
            },
        )
        return decision

    def arbitrate_crew_proposals(
        self,
        decision: dict,
        crew_proposals: list[dict],
        student_state: dict,
    ) -> dict:
        if not crew_proposals:
            fallback = {
                "proposal_id": "fallback",
                "owner_agent": "system",
                "learning_path": "",
                "quiz": [],
                "teacher_style": "",
                "rag_chunks": [],
                "engineered_query": "",
                "confidence": 0.0,
                "challenge_level": "medium",
                "execution_cost": 1.0,
                "decision": decision,
            }
            trace_event("arbitration_selected", {"selected": fallback["proposal_id"], "score": 0.0})
            return fallback

        action = decision.get("action", "adjust_quiz")
        style = student_state.get("learning_style", "balanced")
        low_support_actions = {"increase_challenge", "challenge_with_variation", "advance_topic"}

        def _proposal_score(proposal: dict) -> float:
            confidence = float(proposal.get("confidence", 0.5))
            cost = float(proposal.get("execution_cost", 1.0))
            challenge = str(proposal.get("challenge_level", "medium"))
            owner = proposal.get("owner_agent", "unknown")

            score = confidence * 0.6 - cost * 0.15
            if action in low_support_actions and challenge in ("medium", "high"):
                score += 0.2
            if action in ("increase_support", "reinforce_basics") and challenge == "low":
                score += 0.2
            if style == "visual" and owner == "teacher_persona":
                score += 0.1
            if style == "problem-solver" and owner == "practical_agent":
                score += 0.1
            return score

        scored = [
            {"proposal_id": p.get("proposal_id"), "owner_agent": p.get("owner_agent"), "score": round(_proposal_score(p), 4)}
            for p in crew_proposals
        ]
        selected = max(crew_proposals, key=_proposal_score).copy()
        selected["decision"] = decision
        trace_event(
            "arbitration_selected",
            {
                "selected": selected.get("proposal_id"),
                "owner_agent": selected.get("owner_agent"),
                "scores": scored,
            },
        )
        return selected
