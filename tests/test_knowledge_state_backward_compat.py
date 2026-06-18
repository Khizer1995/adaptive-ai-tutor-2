from core.knowledge_state_updater import ensure_knowledge_state, apply_execution_feedback, record_assessment_score
from core.student_profile_schema import StudentProfile


def test_schema_backward_compat_without_knowledge_state():
    legacy = {
        "student_id": "LEGACY-1",
        "name": "Legacy Student",
        "level": "beginner",
        "progress": [],
        "engagement": "medium",
        "last_score": 0.4,
        "learning_history": [],
    }
    profile = StudentProfile.from_dict(legacy)
    payload = profile.to_dict()
    assert "knowledge_state" in payload
    assert payload["knowledge_state"]["version"] == 1


def test_knowledge_state_updates_without_breaking_progress():
    student_state = {
        "student_id": "TEST-1",
        "level": "beginner",
        "progress": [],
        "engagement": "medium",
        "last_score": 0.3,
        "learning_history": [],
        "current_topic": "arrays",
    }
    ensure_knowledge_state(student_state)
    updated = apply_execution_feedback(
        student_state,
        {"topic": "arrays", "observed_score": 0.8, "observed_engagement": "high"},
        {"scaffold_policy": "medium"},
    )
    assert "knowledge_state" in updated
    assert "arrays" in updated["knowledge_state"]["concepts"]


def test_pre_post_assessment_learning_gain_is_stored():
    student_state = {"student_id": "TEST-1"}

    record_assessment_score(student_state, "stack", "stack_push", "pretest", 0.25)
    record_assessment_score(student_state, "stack", "stack_push", "posttest", 0.75)

    assert student_state["pretest_score"] == 0.25
    assert student_state["posttest_score"] == 0.75
    assert student_state["learning_gain"] == 0.5
    assert student_state["normalized_learning_gain"] == round(0.5 / 0.75, 4)
    assert student_state["assessment_scores"]["stack"]["stack_push"]["learning_gain"] == 0.5
    assert student_state["assessment_history"][-1]["type"] == "posttest"
