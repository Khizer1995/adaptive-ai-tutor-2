from fastapi.testclient import TestClient
from pathlib import Path
from uuid import uuid4

import api_server


def test_study_survey_stores_jsonl_and_returns_table_means(monkeypatch) -> None:
    survey_path = Path("data") / f"survey_responses_{uuid4().hex}.jsonl"
    survey_path.unlink(missing_ok=True)
    monkeypatch.setattr(api_server, "SURVEY_RESPONSES_PATH", survey_path)
    monkeypatch.setattr(
        api_server,
        "get_student_state",
        lambda: {
            "student_id": "KISH-001",
            "current_topic": "stack",
            "current_subtopic": "stack_push",
        },
    )

    client = TestClient(api_server.app)
    responses = {question["id"]: 4 for question in api_server.SURVEY_QUESTIONS}
    responses["usability_easy_to_use"] = 5

    submit = client.post(
        "/study/survey",
        json={
            "responses": responses,
            "liked_most": "Clear explanations",
            "improve": "More examples",
        },
    )

    assert submit.status_code == 200
    assert submit.json()["status"] == "stored"
    assert survey_path.exists()

    results = client.get("/study/results")
    assert results.status_code == 200
    payload = results.json()
    assert payload["table"] == "Table 2"
    assert payload["response_count"] == 1
    first_row = payload["questions"][0]
    assert first_row["question_id"] == "usability_easy_to_use"
    assert first_row["mean"] == 5.0
    assert first_row["count"] == 1
    survey_path.unlink(missing_ok=True)
