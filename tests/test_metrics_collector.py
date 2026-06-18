from core.metrics_collector import collect_learning_cycle_metrics, log_learning_cycle_metrics


def test_collect_learning_cycle_metrics_has_required_fields() -> None:
    metrics = collect_learning_cycle_metrics(
        student_state={
            "last_score": 0.8,
            "learning_history": [{"score": 0.8}],
        },
        macro_decision={"macro_action": "guided_progression", "scaffold_policy": "medium"},
        micro_decision={"action": "advance_topic"},
        crew_output={
            "learning_path": "Stack follows LIFO.",
            "validation_status": "passed",
            "teacher_style": "balanced",
            "decision": {"action": "advance_topic"},
            "rag_chunk_records": [
                {
                    "metadata": {
                        "source": "pdf_stack_and_queues",
                        "source_ref": "data/raw/Stack.pdf",
                    }
                },
                {
                    "metadata": {
                        "source": "opendsa",
                        "source_ref": "https://example.com/stack",
                    }
                },
            ],
        },
        timings={
            "rag_latency_ms": 12.5,
            "crewai_latency_ms": 34.2,
            "e2e_latency_ms": 56.7,
        },
        decision_iterations=2,
    )

    assert metrics["rag_latency_ms"] == 12.5
    assert metrics["crewai_latency_ms"] == 34.2
    assert metrics["e2e_latency_ms"] == 56.7
    assert 0.0 <= metrics["validation_score"] <= 1.0
    assert metrics["validation_checks_passed"]["validation_status_passed"] is True
    assert metrics["scaffolding_direction"] == "advanced"
    assert metrics["decision_iterations"] == 2
    assert metrics["macro_decision"] == "guided_progression"
    assert metrics["micro_decision"] == "advance_topic"
    assert metrics["source_types_used"] == ["pdf", "url"]
    assert metrics["quiz_pass_rate"] == 0.8


def test_log_learning_cycle_metrics_appends_jsonl_payload(monkeypatch) -> None:
    captured = []

    def fake_log_jsonl(filename, payload):
        captured.append((filename, payload))

    monkeypatch.setattr("core.metrics_collector.log_jsonl", fake_log_jsonl)

    metrics = log_learning_cycle_metrics(
        student_state={"last_score": 0.3},
        macro_decision={"macro_action": "stabilize_foundations", "scaffold_policy": "high"},
        micro_decision={"action": "increase_support"},
        crew_output={"validation_status": "failed"},
        timings={},
        decision_iterations=1,
        quiz_pass_rate=0.3,
    )

    assert captured == [("metrics_log.jsonl", metrics)]
    assert metrics["scaffolding_direction"] == "increased_support"
