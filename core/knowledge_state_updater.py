from typing import Any, Dict


def ensure_knowledge_state(student_state: Dict[str, Any]) -> Dict[str, Any]:
    knowledge_state = student_state.get("knowledge_state")
    if not isinstance(knowledge_state, dict):
        knowledge_state = {"concepts": {}, "version": 1}
        student_state["knowledge_state"] = knowledge_state
    concepts = knowledge_state.get("concepts")
    if not isinstance(concepts, dict):
        knowledge_state["concepts"] = {}
    return student_state


def _assessment_entry(student_state: Dict[str, Any], topic: str, subtopic: str) -> Dict[str, Any]:
    assessments = student_state.setdefault("assessment_scores", {})
    topic_entry = assessments.setdefault(topic, {})
    return topic_entry.setdefault(subtopic, {})


def record_assessment_score(
    student_state: Dict[str, Any],
    topic: str,
    subtopic: str,
    assessment_type: str,
    score: float,
) -> Dict[str, Any]:
    score = round(max(0.0, min(1.0, float(score))), 4)
    entry = _assessment_entry(student_state, topic, subtopic)

    if assessment_type == "pretest":
        entry["pretest_score"] = score
        student_state["pretest_score"] = score
    elif assessment_type == "posttest":
        entry["posttest_score"] = score
        student_state["posttest_score"] = score
    else:
        raise ValueError(f"Unsupported assessment_type: {assessment_type}")

    pretest_score = entry.get("pretest_score")
    posttest_score = entry.get("posttest_score")
    student_state.setdefault("assessment_history", []).append(
        {
            "type": assessment_type,
            "topic": topic,
            "subtopic": subtopic,
            "score": score,
        }
    )
    student_state["last_assessment_type"] = assessment_type

    if pretest_score is not None and posttest_score is not None:
        learning_gain = round(float(posttest_score) - float(pretest_score), 4)
        denominator = 1.0 - float(pretest_score)
        normalized_learning_gain = 0.0
        if denominator > 0:
            normalized_learning_gain = round((float(posttest_score) - float(pretest_score)) / denominator, 4)
        entry["learning_gain"] = learning_gain
        entry["normalized_learning_gain"] = normalized_learning_gain
        student_state["learning_gain"] = learning_gain
        student_state["normalized_learning_gain"] = normalized_learning_gain
        student_state.setdefault("learning_gain_events", []).append(
            {
                "topic": topic,
                "subtopic": subtopic,
                "pretest_score": round(float(pretest_score), 4),
                "posttest_score": round(float(posttest_score), 4),
                "learning_gain": learning_gain,
                "normalized_learning_gain": normalized_learning_gain,
            }
        )

    return student_state


def apply_execution_feedback(
    student_state: Dict[str, Any],
    execution_feedback: Dict[str, Any],
    macro_decision: Dict[str, Any],
) -> Dict[str, Any]:
    student_state = ensure_knowledge_state(student_state)
    knowledge_state = student_state["knowledge_state"]
    concepts = knowledge_state["concepts"]

    topic = execution_feedback.get("topic") or student_state.get("current_topic") or "general"
    score = float(execution_feedback.get("observed_score", student_state.get("last_score", 0.0)))
    engagement = execution_feedback.get("observed_engagement", student_state.get("engagement", "medium"))
    confidence_signal = {"low": 0.35, "medium": 0.6, "high": 0.8}.get(engagement, 0.6)

    concept_state = concepts.get(topic, {})
    prev_mastery = float(concept_state.get("mastery", 0.0))
    prev_confidence = float(concept_state.get("confidence", 0.5))
    attempts = int(concept_state.get("attempts", 0)) + 1

    mastery = round((0.7 * prev_mastery) + (0.3 * score), 3)
    confidence = round((0.8 * prev_confidence) + (0.2 * confidence_signal), 3)

    scaffold_policy = macro_decision.get("scaffold_policy", "medium")
    if mastery < 0.45 or confidence < 0.45:
        scaffold_level = "high"
    elif mastery > 0.75 and confidence > 0.7:
        scaffold_level = "low"
    else:
        scaffold_level = scaffold_policy

    concept_state.update(
        {
            "mastery": mastery,
            "confidence": confidence,
            "scaffold_level": scaffold_level,
            "attempts": attempts,
        }
    )
    concepts[topic] = concept_state

    progress = student_state.get("progress", [])
    if mastery >= 0.65 and confidence >= 0.55 and topic not in progress:
        progress.append(topic)
        student_state["progress"] = progress

    concept_values = list(concepts.values())
    avg_mastery = (
        sum(float(c.get("mastery", 0.0)) for c in concept_values) / len(concept_values)
        if concept_values
        else 0.0
    )
    if avg_mastery > 0.8 and student_state.get("level") == "intermediate":
        student_state["level"] = "advanced"
    elif avg_mastery > 0.6 and student_state.get("level") == "beginner":
        student_state["level"] = "intermediate"

    student_state.setdefault("knowledge_events", []).append(
        {
            "topic": topic,
            "mastery": mastery,
            "confidence": confidence,
            "scaffold_level": scaffold_level,
            "observed_score": score,
        }
    )
    return student_state
