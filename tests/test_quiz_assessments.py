from fastapi.testclient import TestClient

import api_server


def _answer(question: str, selected: str, correct: str) -> dict:
    return {
        "question": question,
        "selected_answer": selected,
        "correct_answer": correct,
    }


def test_pretest_and_posttest_scores_store_learning_gain(monkeypatch) -> None:
    state = {
        "student_id": "KISH-001",
        "name": "Student",
        "subject": "dsa",
        "level": "beginner",
        "current_topic": "stack",
        "current_subtopic": "stack_push",
        "last_score": 0.0,
        "learning_history": [],
    }

    def fake_get_student_state():
        return state

    def fake_save(student_id, updated_state):
        persisted = dict(updated_state)
        state.clear()
        state.update(persisted)

    monkeypatch.setattr(api_server, "get_student_state", fake_get_student_state)
    monkeypatch.setattr(api_server.pm, "save", fake_save)

    client = TestClient(api_server.app)
    pretest = client.post(
        "/quiz/pretest",
        json={
            "topic": "stack",
            "subtopic": "stack_push",
            "answers": [
                _answer("What is push?", "correct", "correct"),
                _answer("What is stack?", "wrong", "correct"),
            ],
        },
    )
    assert pretest.status_code == 200
    assert pretest.json()["type"] == "pretest"
    assert pretest.json()["score"] == 0.5

    posttest = client.post(
        "/quiz/posttest",
        json={
            "topic": "stack",
            "subtopic": "stack_push",
            "answers": [
                _answer("What is push?", "correct", "correct"),
                _answer("What is stack?", "correct", "correct"),
            ],
        },
    )
    assert posttest.status_code == 200
    payload = posttest.json()
    assert payload["type"] == "posttest"
    assert payload["pretest_score"] == 0.5
    assert payload["posttest_score"] == 1.0
    assert payload["learning_gain"] == 0.5
    assert payload["normalized_learning_gain"] == 1.0

    student_state = client.get("/student/state").json()
    assert student_state["learning_gain"] == 0.5
    assert student_state["normalized_learning_gain"] == 1.0
    assert student_state["pretest_score"] == 0.5
    assert student_state["posttest_score"] == 1.0
