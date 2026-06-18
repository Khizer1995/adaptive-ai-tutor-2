from core.monitor_agent import MonitorAgent


def test_monitor_preserves_quiz_score_and_history() -> None:
    monitor = MonitorAgent()
    student_state = {
        "current_topic": "stack",
        "last_score": 0.82,
        "engagement": "medium",
        "learning_history": [{"topic": "stack", "score": 0.82, "question_count": 6}],
    }
    original_history = list(student_state["learning_history"])

    result = monitor.interact(
        {
            "owner_agent": "tutor_agent",
            "challenge_level": "high",
        },
        student_state,
    )

    assert student_state["last_score"] == 0.82
    assert student_state["learning_history"] == original_history
    assert result["execution_feedback"]["observed_score"] == 0.82
    assert result["updated_student_state"]["last_score"] == 0.82


def test_monitor_updates_engagement_deterministically_from_current_score() -> None:
    monitor = MonitorAgent()
    student_state = {
        "current_topic": "queue",
        "last_score": 0.35,
        "engagement": "high",
        "learning_history": [],
    }

    result = monitor.interact(
        {
            "owner_agent": "practical_agent",
            "challenge_level": "low",
        },
        student_state,
    )

    assert result["updated_student_state"]["engagement"] == "low"
    assert result["execution_feedback"]["observed_engagement"] == "low"
    assert result["execution_feedback"]["observed_score"] == 0.35
