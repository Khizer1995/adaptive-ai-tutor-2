from dataclasses import dataclass
from core.logging_utils import get_logger, log_jsonl, trace_event


@dataclass
class AblationConfig:
    use_arbitration: bool = True
    use_mastery_rerank: bool = True
    use_validation: bool = True


class DecisionEngine:
    """
    Adaptive Decision Engine

    Features:
    - Performance-based adaptation
    - Engagement-aware routing
    - Learning trend analysis
    - Deterministic weight-based decision rules
    """

    def __init__(self, ablation_config: AblationConfig | None = None):
        self.ablation_config = ablation_config or AblationConfig()
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

    @staticmethod
    def _cycle_index(student_state: dict) -> int:
        history = student_state.get("learning_history", [])
        return len(history) + 1

    @staticmethod
    def _join_rationale(lines: list[str]) -> str:
        return " | ".join(line.strip() for line in lines if line and line.strip())

    def _log_decision(self, decision_type: str, student_state: dict, payload: dict) -> None:
        log_jsonl(
            "decision_log.jsonl",
            {
                "decision_type": decision_type,
                "cycle_index": self._cycle_index(student_state),
                "student_id": student_state.get("student_id"),
                "topic": student_state.get("current_topic"),
                "subtopic": student_state.get("current_subtopic"),
                "last_score": student_state.get("last_score"),
                "engagement": student_state.get("engagement"),
                "decision_payload": payload,
                "decision_rationale": payload.get("decision_rationale", ""),
            },
        )

    @staticmethod
    def _select_weighted_action(weights: dict[str, int], action_order: list[str]) -> str:
        best_action = action_order[0]
        best_score = weights.get(best_action, 0)
        for action in action_order[1:]:
            score = weights.get(action, 0)
            if score > best_score:
                best_action = action
                best_score = score
        return best_action

    def decide_macro_plan(self, student_state: dict) -> dict:
        score = student_state.get("last_score", 0.0)
        engagement = student_state.get("engagement", "medium")
        trend = self.analyze_learning_trend(student_state)
        avg_mastery, avg_confidence, weakest_concept = self._knowledge_snapshot(student_state)
        rationale_lines: list[str] = []

        if score < 0.45:
            macro_action = "stabilize_foundations"
            scaffold_policy = "high"
            rationale_lines.append(
                f"IF last_score ({score:.2f}) < 0.45 THEN stabilize foundations with high scaffolding."
            )
        elif trend == "declining":
            macro_action = "stabilize_foundations"
            scaffold_policy = "high"
            rationale_lines.append(
                "IF the last three scores are declining THEN stabilize foundations with high scaffolding."
            )
        elif avg_mastery > 0.75 and avg_confidence > 0.7:
            macro_action = "advance_concepts"
            scaffold_policy = "low"
            rationale_lines.append(
                "IF average mastery > 0.75 AND average confidence > 0.70 THEN advance concepts with low scaffolding."
            )
        else:
            macro_action = "guided_progression"
            scaffold_policy = "medium"
            rationale_lines.append(
                "IF the learner is neither at-risk nor clearly ready to accelerate THEN use guided progression with medium scaffolding."
            )

        if engagement == "low" and scaffold_policy != "high":
            scaffold_policy = "medium"
            rationale_lines.append(
                "IF engagement is low THEN do not allow low scaffolding; clamp scaffold policy to medium."
            )

        rationale_lines.append(
            f"Target weakest concept '{weakest_concept}' based on mastery snapshot (avg_mastery={avg_mastery:.2f}, avg_confidence={avg_confidence:.2f}, trend={trend})."
        )
        decision_rationale = self._join_rationale(rationale_lines)

        macro_plan = {
            "macro_action": macro_action,
            "target_concepts": [weakest_concept],
            "scaffold_policy": scaffold_policy,
            "reason": decision_rationale,
            "decision_rationale": decision_rationale,
        }
        self.logger.info(
            f"macro_action={macro_action} scaffold_policy={scaffold_policy} "
            f"score={score} trend={trend} avg_mastery={avg_mastery:.2f} "
            f"avg_confidence={avg_confidence:.2f} rationale={decision_rationale}"
        )
        self._log_decision("macro", student_state, macro_plan)
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
        current_subtopic = student_state.get("current_subtopic")
        actions = [
            "increase_support",
            "reinforce_basics",
            "adjust_quiz",
            "increase_challenge",
            "challenge_with_variation",
            "advance_topic",
            "reduce_support",
        ]
        weights = {action: 0 for action in actions}
        weight_reasons: dict[str, list[str]] = {action: [] for action in actions}

        def add_weight(action: str, amount: int, reason: str) -> None:
            weights[action] += amount
            weight_reasons[action].append(f"+{amount}: {reason}")

        if engagement == "low":
            add_weight("increase_support", 3, "engagement is low")
            add_weight("reinforce_basics", 2, "engagement is low")
        elif engagement == "high":
            add_weight("increase_challenge", 2, "engagement is high")
            add_weight("advance_topic", 2, "engagement is high")

        if trend == "declining":
            add_weight("reinforce_basics", 3, "trend is declining")
            add_weight("increase_support", 2, "trend is declining")
        elif trend == "improving":
            add_weight("advance_topic", 2, "trend is improving")
            add_weight("challenge_with_variation", 2, "trend is improving")

        if score < 0.4:
            add_weight("increase_support", 3, f"last_score {score:.2f} is below 0.40")
            add_weight("reinforce_basics", 2, f"last_score {score:.2f} is below 0.40")
        elif 0.4 <= score < 0.65:
            add_weight("adjust_quiz", 2, f"last_score {score:.2f} is in the guided band")
            if trend == "improving":
                add_weight("increase_challenge", 1, "guided-band score with improving trend")
        else:
            if engagement in ("medium", "high"):
                add_weight("advance_topic", 4, f"last_score {score:.2f} is at least 0.65 and engagement is {engagement}")
            else:
                add_weight("adjust_quiz", 2, f"last_score {score:.2f} is strong but engagement is {engagement}")
            if trend == "improving":
                add_weight("challenge_with_variation", 2, "strong score with improving trend")
            else:
                add_weight("reduce_support", 1, "strong score without improving trend")

        if style == "problem-solver":
            add_weight("increase_challenge", 1, "learning style is problem-solver")
            add_weight("challenge_with_variation", 1, "learning style is problem-solver")
        elif style == "visual":
            add_weight("adjust_quiz", 1, "learning style is visual")

        if scaffold_policy == "high":
            add_weight("increase_support", 2, "macro scaffold policy is high")
            add_weight("reinforce_basics", 1, "macro scaffold policy is high")
        elif scaffold_policy == "low":
            add_weight("advance_topic", 1, "macro scaffold policy is low")
            add_weight("increase_challenge", 1, "macro scaffold policy is low")

        if macro_action == "advance_concepts" and current_subtopic:
            add_weight(
                "advance_topic",
                5,
                "macro action is advance_concepts and a current_subtopic is active",
            )

        best_action = self._select_weighted_action(weights, actions)
        next_node = "monitor_agent" if best_action == "reduce_support" else "education_crew"

        fired_weights = []
        for action in actions:
            if weights[action] > 0:
                fired_weights.append(
                    {
                        "action": action,
                        "total_weight": weights[action],
                        "reasons": weight_reasons[action],
                    }
                )

        if fired_weights:
            rationale_lines = [
                "Deterministic weighted decision with no randomness.",
                *[
                    f"{entry['action']}={entry['total_weight']} from {', '.join(entry['reasons'])}"
                    for entry in fired_weights
                ],
                (
                    f"Selected '{best_action}' because it had the highest total weight ({weights[best_action]}). "
                    f"Ties resolve by fixed action order: {', '.join(actions)}."
                ),
                (
                    f"Context used: score={score:.2f}, engagement={engagement}, trend={trend}, "
                    f"style={style}, macro_action={macro_action or 'none'}, scaffold_policy={scaffold_policy}."
                ),
            ]
        else:
            rationale_lines = [
                "No positive weights fired; defaulted deterministically using fixed action order.",
                f"Selected '{best_action}' with total weight {weights[best_action]}.",
                (
                    f"Context used: score={score:.2f}, engagement={engagement}, trend={trend}, "
                    f"style={style}, macro_action={macro_action or 'none'}, scaffold_policy={scaffold_policy}."
                ),
            ]
        decision_rationale = self._join_rationale(rationale_lines)

        decision = {
            "next_node": next_node,
            "action": best_action,
            "weights": weights,
            "fired_weights": fired_weights,
            "reason": decision_rationale,
            "decision_rationale": decision_rationale,
        }

        self.logger.info(
            f"score={score} engagement={engagement} trend={trend} "
            f"style={style} action={best_action} next_node={next_node} "
            f"rationale={decision_rationale}"
        )
        self._log_decision("micro", student_state, decision)
        trace_event(
            "decision_made",
            {
                "score": score,
                "engagement": engagement,
                "trend": trend,
                "style": style,
                "action": best_action,
                "next_node": next_node,
                "decision_rationale": decision_rationale,
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

        if not self.ablation_config.use_arbitration:
            scored = [
                {"proposal_id": p.get("proposal_id"), "owner_agent": p.get("owner_agent"), "score": round(float(p.get("confidence", 0.0)), 4)}
                for p in crew_proposals
            ]
            selected = max(crew_proposals, key=lambda p: float(p.get("confidence", 0.0))).copy()
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
