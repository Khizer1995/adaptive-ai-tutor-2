from fastapi.testclient import TestClient

import api_server
from core.learning_response_format import SECTION_HEADERS, build_structured_explain_query


def test_bullet_format_contract_template_contains_required_sections() -> None:
    query = build_structured_explain_query("stack", "beginner", "balanced", "DSA")
    for section in SECTION_HEADERS:
        assert section in query
    assert "Simple Explanation:" not in query


def test_explain_response_always_contains_next_recommendation(monkeypatch) -> None:
    def fake_get_student_state():
        return {
            "student_id": "KISH-001",
            "name": "Student",
            "subject": "dsa",
            "level": "beginner",
            "current_topic": "stack",
            "last_score": 0.8,
            "knowledge_state": {"concepts": {"stack": {"confidence": 0.8}}},
            "delivered_chunks": {},
        }

    def fake_run_flow(state, **kwargs):
        return {
            "macro": {"macro_action": "stabilize_foundations"},
            "validated": {
                "learning_path": "• Concept Overview: Stack basics",
                "rag_chunks": ["Stack follows LIFO."],
                "rag_chunk_records": [
                    {
                        "chunk_id": "id1",
                        "content": "Stack follows LIFO.",
                        "metadata": {"topic": "stack", "concept": "definition", "order_index": 1},
                    }
                ],
                "proposal_id": "tutor_plan",
                "validation_status": "passed",
            },
            "monitor_output": {},
            "updated_state": {
                "student_id": "KISH-001",
                "subject": "dsa",
                "current_topic": "stack",
                "last_score": 0.8,
                "knowledge_state": {"concepts": {"stack": {"confidence": 0.8}}},
                "delivered_chunks": {},
            },
        }

    monkeypatch.setattr(api_server, "get_student_state", fake_get_student_state)
    monkeypatch.setattr(api_server, "_run_adaptive_learning_flow", fake_run_flow)
    monkeypatch.setattr(api_server, "_ensure_rag_ready", lambda: {"rag_ready": True})
    monkeypatch.setattr(api_server.pm, "save", lambda student_id, state: None)

    client = TestClient(api_server.app)
    response = client.post("/tutor/explain", json={"topic": "stack"})
    assert response.status_code == 200
    payload = response.json()
    assert "next_recommendation" in payload
    assert isinstance(payload["next_recommendation"], dict)


def test_quiz_chunk_ids_are_subset_of_delivered_chunks(monkeypatch) -> None:
    delivered = ["id1", "id2"]

    def fake_get_student_state():
        return {
            "student_id": "KISH-001",
            "name": "Student",
            "subject": "dsa",
            "level": "beginner",
            "current_topic": "stack",
            "knowledge_state": {"concepts": {"stack": {"confidence": 0.8}}},
            "delivered_chunks": {
                "stack": {
                    "chunk_ids": delivered,
                    "concepts": ["definition", "operations"],
                }
            },
        }

    def fake_retrieve(query, state, k=2, allowed_chunk_ids=None, concept_family=None):
        ids = allowed_chunk_ids or []
        return [
            {
                "chunk_id": cid,
                "content": f"Chunk for {cid}",
                "metadata": {"topic": "stack", "concept": "definition"},
            }
            for cid in ids[:k]
        ]

    monkeypatch.setattr(api_server, "get_student_state", fake_get_student_state)
    monkeypatch.setattr(api_server, "_ensure_rag_ready", lambda: {"rag_ready": True})
    monkeypatch.setattr(
        api_server.crew.practical,
        "generate_quiz_batch",
        lambda micro, state, rag_context, target_count=None, seen_hashes=None: [
            {
                "question": "What is stack?",
                "options": ["Stack follows LIFO.", "Stack follows FIFO.", "Stack is a tree.", "Stack is a graph."],
                "correct_answer": "Stack follows LIFO.",
                "explanation": "A stack removes the newest item first.",
            }
        ],
    )
    monkeypatch.setattr(
        api_server.crew.tutor.query_engineer,
        "engineer",
        lambda prompt, state: "Quiz questions for stack",
    )
    monkeypatch.setattr(api_server.crew.tutor, "retrieve_context_chunk_records", fake_retrieve)

    client = TestClient(api_server.app)
    response = client.post("/quiz/generate", json={"topic": "stack"})
    assert response.status_code == 200
    payload = response.json()
    used = set(payload["quiz_basis"]["chunk_ids_used"])
    assert used.issubset(set(delivered))

