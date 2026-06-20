from __future__ import annotations

import hashlib
import json
import random
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List


LOW_SCORE_THRESHOLD = 0.45
HIGH_SCORE_THRESHOLD = 0.75


def clamp_score(value: Any, default: float = 0.0) -> float:
    try:
        score = float(value)
    except (TypeError, ValueError):
        score = default
    return round(max(0.0, min(1.0, score)), 4)


def canonical_topic(value: str) -> str:
    return str(value or "").strip().lower().replace(" ", "_")


def normalize_text(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()


def stable_hash(value: str) -> str:
    return hashlib.sha256(normalize_text(value).encode("utf-8")).hexdigest()


def ensure_learning_state(student_state: Dict[str, Any]) -> Dict[str, Any]:
    student_state.setdefault("progress", [])
    student_state.setdefault("learning_history", [])
    student_state.setdefault("generated_content_history", {})
    student_state.setdefault("content_fingerprints", {})
    student_state.setdefault("quiz_seen_questions", {})
    student_state.setdefault("quiz_attempts", {})
    student_state.setdefault("weak_areas", {})
    student_state.setdefault("strong_areas", {})
    student_state.setdefault("completed_topics", student_state.get("progress", []))

    knowledge_state = student_state.setdefault("knowledge_state", {})
    knowledge_state.setdefault("version", 2)
    knowledge_state.setdefault("concepts", {})
    return student_state


def topic_state(student_state: Dict[str, Any], topic: str) -> Dict[str, Any]:
    ensure_learning_state(student_state)
    concepts = student_state["knowledge_state"]["concepts"]
    key = canonical_topic(topic)
    return concepts.setdefault(
        key,
        {
            "mastery": clamp_score(student_state.get("last_score", 0.0)),
            "confidence": 0.35,
            "attempts": 0,
            "scaffold_level": "high",
            "weak_areas": [],
            "strong_areas": [],
            "completed": False,
        },
    )


def recent_topic_scores(student_state: Dict[str, Any], topic: str, limit: int = 5) -> List[float]:
    topic_key = canonical_topic(topic)
    scores: List[float] = []
    for item in reversed(student_state.get("learning_history", [])):
        if canonical_topic(str(item.get("topic", ""))) == topic_key and "score" in item:
            scores.append(clamp_score(item.get("score")))
        if len(scores) >= limit:
            break
    return list(reversed(scores))


def adaptive_profile(student_state: Dict[str, Any], topic: str) -> Dict[str, Any]:
    ensure_learning_state(student_state)
    concept = topic_state(student_state, topic)
    scores = recent_topic_scores(student_state, topic)
    score = scores[-1] if scores else clamp_score(student_state.get("last_score", concept.get("mastery", 0.0)))
    mastery = clamp_score(concept.get("mastery", score))
    scaffold = str(concept.get("scaffold_level", "medium"))

    if score < LOW_SCORE_THRESHOLD or mastery < LOW_SCORE_THRESHOLD or scaffold == "high":
        mode = "remedial"
        depth = "beginner"
        requirements = [
            "use beginner-friendly language",
            "break the idea into small chunks",
            "add one analogy and one real-world example",
            "include prerequisite concepts before the main concept",
            "avoid unnecessary complexity until the recap",
            "end with a short remediation practice task",
        ]
    elif score >= HIGH_SCORE_THRESHOLD and mastery >= 0.65:
        mode = "advanced"
        depth = "advanced"
        requirements = [
            "increase technical depth",
            "include edge cases and practical applications",
            "include interview-style questions",
            "compare trade-offs and complexity",
            "avoid repeating basic definitions unless needed",
        ]
    else:
        mode = "guided"
        depth = str(student_state.get("level", "beginner"))
        requirements = [
            "use clear step-by-step explanation",
            "include one fresh example",
            "connect the concept to the learner's recent performance",
            "include a quick self-check",
        ]

    return {
        "mode": mode,
        "depth": depth,
        "last_topic_score": score,
        "mastery": mastery,
        "scaffold_level": scaffold,
        "requirements": requirements,
        "weak_areas": concept.get("weak_areas", []),
        "strong_areas": concept.get("strong_areas", []),
    }


def record_quiz_attempt(
    student_state: Dict[str, Any],
    topic: str,
    subtopic: str,
    score: float,
    answers: Iterable[Any],
) -> Dict[str, Any]:
    ensure_learning_state(student_state)
    topic_key = canonical_topic(topic)
    subtopic_key = str(subtopic or f"{topic_key}_general")
    score = clamp_score(score)
    answers_list = list(answers)
    now = datetime.now(timezone.utc).isoformat()

    attempt = {
        "timestamp": now,
        "topic": topic_key,
        "subtopic": subtopic_key,
        "score": score,
        "question_count": len(answers_list),
    }
    student_state.setdefault("learning_history", []).append(attempt)
    attempts = student_state.setdefault("quiz_attempts", {}).setdefault(topic_key, {}).setdefault(subtopic_key, [])
    attempts.append(attempt)

    concept = topic_state(student_state, topic_key)
    prev_mastery = clamp_score(concept.get("mastery", 0.0))
    prev_confidence = clamp_score(concept.get("confidence", 0.35), 0.35)
    concept["attempts"] = int(concept.get("attempts", 0)) + 1
    concept["mastery"] = round((0.65 * prev_mastery) + (0.35 * score), 4)
    concept["confidence"] = round((0.7 * prev_confidence) + (0.3 * (0.85 if score >= 0.7 else 0.35)), 4)

    missed = [
        normalize_text(getattr(answer, "question", "") or str(getattr(answer, "question", "")))
        for answer in answers_list
        if normalize_text(getattr(answer, "selected_answer", "")) != normalize_text(getattr(answer, "correct_answer", ""))
    ]
    missed = [item for item in missed if item]

    if score < LOW_SCORE_THRESHOLD:
        concept["scaffold_level"] = "high"
        concept["weak_areas"] = sorted(set(concept.get("weak_areas", []) + missed[:5] + [subtopic_key]))
        student_state.setdefault("weak_areas", {}).setdefault(topic_key, [])
        student_state["weak_areas"][topic_key] = sorted(set(student_state["weak_areas"][topic_key] + concept["weak_areas"]))
        student_state["level"] = "beginner"
    elif score >= HIGH_SCORE_THRESHOLD:
        concept["scaffold_level"] = "low"
        concept["strong_areas"] = sorted(set(concept.get("strong_areas", []) + [subtopic_key]))
        student_state.setdefault("strong_areas", {}).setdefault(topic_key, [])
        student_state["strong_areas"][topic_key] = sorted(set(student_state["strong_areas"][topic_key] + concept["strong_areas"]))
        if concept["mastery"] >= 0.75:
            student_state["level"] = "advanced"
    else:
        concept["scaffold_level"] = "medium"

    if concept["mastery"] >= 0.7 and score >= 0.7:
        concept["completed"] = True
        progress = student_state.setdefault("progress", [])
        if topic_key not in progress:
            progress.append(topic_key)
        completed = student_state.setdefault("completed_topics", progress)
        if topic_key not in completed:
            completed.append(topic_key)

    student_state["last_score"] = score
    return student_state


def record_generated_content(
    student_state: Dict[str, Any],
    topic: str,
    subtopic: str,
    content: str,
    metadata: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    ensure_learning_state(student_state)
    topic_key = canonical_topic(topic)
    subtopic_key = str(subtopic or f"{topic_key}_general")
    history = student_state.setdefault("generated_content_history", {}).setdefault(topic_key, {}).setdefault(subtopic_key, [])
    fingerprint = stable_hash(content[:1200])
    history.append(
        {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "fingerprint": fingerprint,
            "preview": str(content or "")[:240],
            "metadata": metadata or {},
        }
    )
    del history[:-8]
    student_state.setdefault("content_fingerprints", {}).setdefault(topic_key, {}).setdefault(subtopic_key, [])
    fingerprints = student_state["content_fingerprints"][topic_key][subtopic_key]
    if fingerprint not in fingerprints:
        fingerprints.append(fingerprint)
    del fingerprints[:-20]
    return student_state


def previous_content_context(student_state: Dict[str, Any], topic: str, subtopic: str) -> str:
    ensure_learning_state(student_state)
    entries = (
        student_state.get("generated_content_history", {})
        .get(canonical_topic(topic), {})
        .get(str(subtopic or f"{canonical_topic(topic)}_general"), [])
    )
    previews = [str(item.get("preview", "")).strip() for item in entries[-3:] if str(item.get("preview", "")).strip()]
    if not previews:
        return "No prior explanation recorded for this subtopic."
    return "\n".join(f"- {preview}" for preview in previews)


def shuffle_question_options(question: Dict[str, Any], salt: str = "") -> Dict[str, Any]:
    copied = dict(question)
    options = [str(option) for option in copied.get("options", []) if str(option).strip()]
    if not options:
        return copied
    seed = int(stable_hash(f"{copied.get('question', '')}|{salt}")[:12], 16)
    rng = random.Random(seed)
    rng.shuffle(options)
    copied["options"] = options
    return copied


def load_source_topics(
    chunks_path: str = "data/processed/layered_chunks.json",
    graph_path: str = "data/processed/topic_dependency_graph.json",
) -> List[Dict[str, Any]]:
    topics: Dict[str, Dict[str, Any]] = {}

    graph_file = Path(graph_path)
    if graph_file.exists():
        try:
            graph = json.loads(graph_file.read_text(encoding="utf-8"))
            if isinstance(graph, dict):
                for index, (name, data) in enumerate(graph.items()):
                    key = canonical_topic(name)
                    topics.setdefault(
                        key,
                        {
                            "name": key,
                            "order_index": index,
                            "source_count": 0,
                            "subtopics": [],
                            "prerequisites": (data or {}).get("prerequisites", []) if isinstance(data, dict) else [],
                            "next_topics": (data or {}).get("next_topics", []) if isinstance(data, dict) else [],
                        },
                    )
        except json.JSONDecodeError:
            pass

    chunks_file = Path(chunks_path)
    if chunks_file.exists():
        try:
            chunks = json.loads(chunks_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            chunks = []
        if isinstance(chunks, list):
            for item in chunks:
                if not isinstance(item, dict):
                    continue
                topic = canonical_topic(str(item.get("topic", "")))
                if not topic:
                    continue
                entry = topics.setdefault(
                    topic,
                    {
                        "name": topic,
                        "order_index": int(item.get("order_index", 999999) or 999999),
                        "source_count": 0,
                        "subtopics": [],
                        "prerequisites": [],
                        "next_topics": [],
                    },
                )
                entry["source_count"] = int(entry.get("source_count", 0)) + 1
                entry["order_index"] = min(int(entry.get("order_index", 999999)), int(item.get("order_index", 999999) or 999999))
                concept = str(item.get("concept", "")).strip()
                if concept and concept not in entry["subtopics"]:
                    entry["subtopics"].append(concept)

    return sorted(topics.values(), key=lambda item: (int(item.get("order_index", 999999)), item["name"]))
