from core.validation_agent import ValidationAgent


def _long_stack_push_explanation() -> str:
    base = (
        "Stack push adds a new value to the top of the stack while preserving the LIFO rule. "
        "A beginner should read push as placing one more plate on top of an existing pile. "
        "The operation changes only the top position, so the newest item becomes the first item removed later. "
        "This simple step by step view keeps the stack state predictable and easy to trace. "
        "In an array backed stack, push usually writes the value at the next free index and then moves the top marker forward. "
        "Before pushing, implementation code should check capacity so overflow is handled clearly. "
        "The idea is useful in function calls, undo history, expression evaluation, and backtracking. "
        "When learning push, focus on the current top, the inserted value, and the new top after insertion. "
    )
    return base + "\n```python\nstack.append(value)\n```"


def test_validation_agent_passes_grounded_dsa_content(monkeypatch) -> None:
    captured = []

    def fake_log_jsonl(filename, payload):
        captured.append((filename, payload))

    monkeypatch.setattr("core.validation_agent.log_jsonl", fake_log_jsonl)

    agent = ValidationAgent()
    result = agent.validate_content(
        {
            "learning_path": _long_stack_push_explanation(),
            "teacher_style": "Supportive Tutor",
            "decision": {"action": "increase_support"},
            "quiz": [
                {"question": "What does stack push do to the top item?"},
                {"question": "Why does push matter in a stack implementation?"},
            ],
        },
        {
            "student_id": "TEST-1",
            "subject": "dsa",
            "current_topic": "stack",
            "current_subtopic": "stack_push",
            "last_score": 0.3,
        },
    )

    validation = result["validation_result"]
    assert validation["passed"] is True
    assert validation["score"] == 1.0
    assert result["validation_status"] == "passed"
    assert result["adaptive_delivery_level"] == "simplified"
    assert captured[0][0] == "validation_log.jsonl"


def test_validation_agent_flags_failed_checks(monkeypatch) -> None:
    monkeypatch.setattr("core.validation_agent.log_jsonl", lambda filename, payload: None)

    agent = ValidationAgent()
    result = agent.validate_content(
        {
            "learning_path": "As an AI, I cannot explain this.",
            "quiz": [{"question": "What is a queue?"}],
        },
        {
            "subject": "dsa",
            "current_topic": "stack",
            "current_subtopic": "stack_push",
            "last_score": 0.9,
        },
    )

    validation = result["validation_result"]
    assert validation["passed"] is False
    assert result["validation_status"] == "failed"
    assert "hallucination_signal:as an ai" in validation["flags"]
    assert "code_presence" in validation["flags"]
    assert "quiz_alignment" in validation["flags"]
    assert result["adaptive_delivery_level"] == "advanced"
