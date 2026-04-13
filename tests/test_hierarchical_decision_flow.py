from core.decision_engine import DecisionEngine


def test_macro_and_micro_decision_paths():
    engine = DecisionEngine()
    student_state = {
        "last_score": 0.35,
        "engagement": "medium",
        "learning_history": [{"score": 0.55}, {"score": 0.45}, {"score": 0.35}],
        "learning_style": "balanced",
        "knowledge_state": {
            "concepts": {"arrays": {"mastery": 0.3, "confidence": 0.4}},
            "version": 1,
        },
    }
    macro = engine.decide_macro_plan(student_state)
    assert macro["scaffold_policy"] == "high"

    student_state["macro_decision"] = macro
    micro = engine.decide_next_step(student_state)
    assert micro["next_node"] in {"education_crew", "monitor_agent"}
    assert isinstance(micro.get("weights"), dict)


def test_arbitration_prefers_support_on_low_performance():
    engine = DecisionEngine()
    decision = {"action": "increase_support"}
    student_state = {"learning_style": "balanced"}
    proposals = [
        {
            "proposal_id": "p1",
            "owner_agent": "tutor_agent",
            "confidence": 0.7,
            "challenge_level": "low",
            "execution_cost": 0.6,
        },
        {
            "proposal_id": "p2",
            "owner_agent": "practical_agent",
            "confidence": 0.8,
            "challenge_level": "high",
            "execution_cost": 0.5,
        },
    ]
    selected = engine.arbitrate_crew_proposals(decision, proposals, student_state)
    assert selected["proposal_id"] == "p1"
