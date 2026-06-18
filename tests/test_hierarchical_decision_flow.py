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
    assert isinstance(macro.get("decision_rationale"), str)
    assert macro["decision_rationale"]

    student_state["macro_decision"] = macro
    micro = engine.decide_next_step(student_state)
    assert micro["next_node"] in {"education_crew", "monitor_agent"}
    assert isinstance(micro.get("weights"), dict)
    assert isinstance(micro.get("fired_weights"), list)
    assert isinstance(micro.get("decision_rationale"), str)
    assert micro["decision_rationale"]
    assert "Deterministic weighted decision" in micro["decision_rationale"]


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


def test_decision_engine_logs_macro_and_micro_rationales(monkeypatch):
    captured = []

    def fake_log_jsonl(filename, payload):
        captured.append((filename, payload))

    monkeypatch.setattr("core.decision_engine.log_jsonl", fake_log_jsonl)

    engine = DecisionEngine()
    student_state = {
        "student_id": "TEST-DECISION-1",
        "current_topic": "stack",
        "current_subtopic": "stack_push",
        "last_score": 0.82,
        "engagement": "high",
        "learning_style": "problem-solver",
        "learning_history": [{"score": 0.6}, {"score": 0.7}, {"score": 0.82}],
        "knowledge_state": {
            "concepts": {"stack": {"mastery": 0.81, "confidence": 0.76}},
            "version": 1,
        },
    }

    macro = engine.decide_macro_plan(student_state)
    student_state["macro_decision"] = macro
    micro = engine.decide_next_step(student_state)

    assert len(captured) == 2
    assert captured[0][0] == "decision_log.jsonl"
    assert captured[1][0] == "decision_log.jsonl"
    assert captured[0][1]["decision_type"] == "macro"
    assert captured[1][1]["decision_type"] == "micro"
    assert captured[0][1]["decision_rationale"] == macro["decision_rationale"]
    assert captured[1][1]["decision_rationale"] == micro["decision_rationale"]
    assert isinstance(captured[1][1]["decision_payload"]["weights"], dict)
    assert isinstance(captured[1][1]["decision_payload"]["fired_weights"], list)
