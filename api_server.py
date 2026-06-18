from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from dotenv import load_dotenv
import os
import json
import asyncio
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List
from difflib import get_close_matches

load_dotenv()

from core.simulation import AdaptiveLearningSimulation
from core.profile_manager import ProfileManager
from core.decision_engine import DecisionEngine
from core.education_crew import EducationCrew
from core.file_manager_agent import FileManagerAgent
from core.monitor_agent import MonitorAgent
from core.validation_agent import ValidationAgent
from core.knowledge_state_updater import apply_execution_feedback, record_assessment_score
from core.delivery_tracker import append_delivered_chunks, get_delivered_topic_summary
from core.learning_navigation import build_next_recommendation
from core.curriculum_config import UNLOCK_THRESHOLD, get_next_subtopic
from core.practical_agent import QuizQuestion
from core.logging_utils import Timer
from core.metrics_collector import log_learning_cycle_metrics

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

simulation = AdaptiveLearningSimulation()
pm = ProfileManager()
decision_engine = DecisionEngine()
crew = EducationCrew()
file_manager = FileManagerAgent()
monitor_agent = MonitorAgent()
validation_agent = ValidationAgent()

STUDENT_ID = "KISH-001"
SURVEY_RESPONSES_PATH = Path("data/survey_responses.jsonl")
SURVEY_QUESTIONS: List[Dict[str, str]] = [
    {
        "id": "usability_easy_to_use",
        "section": "Usability",
        "question": "The system was easy to use",
    },
    {
        "id": "usability_clear_explanations",
        "section": "Usability",
        "question": "The explanations were clear and understandable",
    },
    {
        "id": "usability_quiz_alignment",
        "section": "Usability",
        "question": "The quizzes matched what I just learned",
    },
    {
        "id": "usability_adapted_level",
        "section": "Usability",
        "question": "The system felt like it adapted to my level",
    },
    {
        "id": "usability_use_again",
        "section": "Usability",
        "question": "I would use this system again to learn a new topic",
    },
    {
        "id": "trust_explanations",
        "section": "Trust",
        "question": "I trusted the system's explanations",
    },
    {
        "id": "trust_hints",
        "section": "Trust",
        "question": "The system gave me appropriate hints",
    },
    {
        "id": "trust_learning_needs",
        "section": "Trust",
        "question": "I felt the system understood my learning needs",
    },
    {
        "id": "engagement_throughout",
        "section": "Engagement",
        "question": "I was engaged throughout the session",
    },
    {
        "id": "engagement_difficulty",
        "section": "Engagement",
        "question": "The difficulty felt appropriate for me",
    },
    {
        "id": "engagement_progress",
        "section": "Engagement",
        "question": "I felt I made progress",
    },
]

from core.teacher_review_agent import TeacherReviewAgent
original_review = TeacherReviewAgent.review


def auto_approve_review(self, crew_output, student_state):
    return {"review_status": "approved", "comments": "auto-approved via API"}


TeacherReviewAgent.review = auto_approve_review


def get_student_state():
    try:
        return pm.load(STUDENT_ID)
    except FileNotFoundError:
        return {
            "student_id": STUDENT_ID,
            "name": "Student",
            "subject": "dsa",
            "level": "beginner",
            "current_topic": "stack",
            "progress": [],
            "engagement": "medium",
            "last_score": 0.3,
            "learning_history": [],
            "knowledge_state": {
                "concepts": {
                    "stack": {
                        "mastery": 0.2,
                        "confidence": 0.25,
                        "attempts": 0,
                        "scaffold_level": "high",
                    }
                },
                "version": 1,
            },
            "delivered_chunks": {},
            "quiz_seen_questions": {},
        }


def _question_hash(question: str) -> str:
    return hashlib.md5(str(question or "").strip().lower().encode("utf-8")).hexdigest()


def _get_seen_hashes_for_subtopic(state: Dict[str, Any], topic: str, subtopic: str) -> set[str]:
    quiz_seen = state.setdefault("quiz_seen_questions", {})
    topic_map = quiz_seen.setdefault(topic, {})
    values = topic_map.setdefault(subtopic, [])
    return {str(v) for v in values}


def _store_seen_hashes_for_subtopic(
    state: Dict[str, Any],
    topic: str,
    subtopic: str,
    seen_hashes: set[str],
) -> None:
    quiz_seen = state.setdefault("quiz_seen_questions", {})
    topic_map = quiz_seen.setdefault(topic, {})
    topic_map[subtopic] = sorted(seen_hashes)


def _reset_seen_hashes_for_other_subtopics(state: Dict[str, Any], topic: str, active_subtopic: str) -> None:
    quiz_seen = state.setdefault("quiz_seen_questions", {})
    topic_map = quiz_seen.setdefault(topic, {})
    for key in list(topic_map.keys()):
        if key != active_subtopic:
            topic_map.pop(key, None)


def _ensure_rag_ready() -> Dict[str, Any]:
    try:
        return file_manager.prepare_knowledge_base(force_reingest=False)
    except Exception as exc:
        return {
            "rag_ready": False,
            "status": "failed",
            "detail": str(exc),
        }


def _format_macro_reason(macro: Dict[str, Any]) -> str:
    return (
        macro.get("reason", "")
        .replace("macro_action=", "Action: ")
        .replace("based on score=", "based on your score of ")
        .replace("trend=", "learning trend: ")
        .replace("avg_mastery=", "average mastery: ")
        .replace("avg_confidence=", "average confidence: ")
        .replace(",", " |")
        or "Content selected based on your current mastery level."
    )


def _parse_json_array(raw: str) -> List[Dict[str, Any]]:
    payload = raw.strip()
    if "```" in payload:
        parts = payload.split("```")
        if len(parts) >= 2:
            payload = parts[1]
            if payload.strip().lower().startswith("json"):
                payload = payload.strip()[4:]
    parsed = json.loads(payload.strip())
    if isinstance(parsed, list):
        return [x for x in parsed if isinstance(x, dict)]
    return []


def _fallback_mcq_questions(topic: str, seeds: List[str]) -> List[Dict[str, Any]]:
    fallback: List[Dict[str, Any]] = []
    for seed in seeds[:3]:
        q_text = seed.strip() or f"Which statement best describes {topic}?"
        correct = f"{topic} is used to solve practical programming tasks."
        options = [
            correct,
            f"{topic} is only a UI concept and not used in Python code.",
            f"{topic} cannot be tested using quiz questions.",
            f"{topic} replaces all Python fundamentals automatically.",
        ]
        fallback.append(
            {
                "question": q_text,
                "options": options,
                "correct_answer": correct,
                "explanation": f"This option correctly captures the purpose of {topic}.",
                "hint": f"Focus on how {topic} is used in real learning tasks.",
            }
        )
    return fallback


def _run_adaptive_learning_flow(
    state: Dict[str, Any],
    rag_status: Dict[str, Any] | None = None,
    quiz_pass_rate: float | None = None,
) -> Dict[str, Any]:
    e2e_timer = Timer()
    macro = decision_engine.decide_macro_plan(state)
    state["macro_decision"] = macro
    decision = decision_engine.decide_next_step(state)
    state["decision"] = decision

    crew_ms = 0.0
    if decision.get("next_node") == "education_crew":
        crew_timer = Timer()
        crew_state = crew.run({"decision": decision, "student_state": state})
        selected = decision_engine.arbitrate_crew_proposals(
            decision, crew_state.get("crew_proposals", []), state
        )
        crew_ms = round(crew_timer.elapsed_ms(), 2)
    else:
        selected = {
            "proposal_id": "monitor_only",
            "owner_agent": "system",
            "learning_path": (
                f"### {state.get('current_topic', 'Current topic')}\n\n"
                "Maintaining momentum with lighter support for this step."
            ),
            "quiz": [],
            "teacher_style": "",
            "rag_chunks": [],
            "engineered_query": "",
            "confidence": 0.5,
            "challenge_level": "low",
            "execution_cost": 0.2,
            "decision": decision,
        }

    validated = validation_agent.validate_content(selected, state)
    monitor_out = monitor_agent.interact(validated, state)
    updated_state = monitor_out.get("updated_student_state", state)
    updated_state = apply_execution_feedback(
        updated_state,
        monitor_out.get("execution_feedback", {}),
        macro,
    )
    rag_chunk_records = validated.get("rag_chunk_records", []) or []
    log_learning_cycle_metrics(
        student_state=updated_state,
        macro_decision=macro,
        micro_decision=decision,
        crew_output=validated,
        timings={
            "rag_latency_ms": (rag_status or {}).get("duration_ms", 0.0),
            "crewai_latency_ms": crew_ms,
            "e2e_latency_ms": round(e2e_timer.elapsed_ms(), 2),
        },
        rag_chunk_records=rag_chunk_records,
        decision_iterations=1,
        quiz_pass_rate=quiz_pass_rate,
    )
    pm.save(STUDENT_ID, updated_state)
    return {
        "macro": macro,
        "decision": decision,
        "validated": validated,
        "monitor_output": monitor_out,
        "updated_state": updated_state,
    }


class TopicRequest(BaseModel):
    topic: str
    subtopic: str | None = None


class QuizAnswerRequest(BaseModel):
    question: str
    selected_answer: str
    correct_answer: str
    topic: str


class QuizBatchAnswer(BaseModel):
    question: str
    selected_answer: str
    correct_answer: str


class AssessmentRequest(BaseModel):
    topic: str
    subtopic: str | None = None
    answers: List[QuizBatchAnswer] | None = None


class QuizBatchSubmitRequest(BaseModel):
    topic: str
    subtopic: str
    score: float | None = None
    answers: List[QuizBatchAnswer]


class CurriculumNextRequest(BaseModel):
    current_topic: str
    current_subtopic: str


class StudySurveyRequest(BaseModel):
    responses: Dict[str, int]
    liked_most: str | None = None
    improve: str | None = None
    topic: str | None = None
    subtopic: str | None = None
    student_id: str | None = None


def _sse_delta(delta: str, done: bool = False, meta: Dict[str, Any] | None = None) -> str:
    payload: Dict[str, Any] = {"delta": delta}
    if done:
        payload["done"] = True
    if meta:
        payload["meta"] = meta
    return f"data: {json.dumps(payload)}\n\n"


def _survey_question_ids() -> set[str]:
    return {question["id"] for question in SURVEY_QUESTIONS}


def _validated_survey_scores(responses: Dict[str, int]) -> Dict[str, int]:
    expected_ids = _survey_question_ids()
    missing = sorted(expected_ids - set(responses.keys()))
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Missing survey responses for: {', '.join(missing)}",
        )

    validated: Dict[str, int] = {}
    for question_id in expected_ids:
        value = responses.get(question_id)
        if not isinstance(value, int) or value < 1 or value > 5:
            raise HTTPException(
                status_code=400,
                detail=f"Survey response '{question_id}' must be an integer from 1 to 5.",
            )
        validated[question_id] = value
    return validated


def _append_survey_response(payload: Dict[str, Any]) -> None:
    SURVEY_RESPONSES_PATH.parent.mkdir(parents=True, exist_ok=True)
    with SURVEY_RESPONSES_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _read_survey_responses() -> List[Dict[str, Any]]:
    if not SURVEY_RESPONSES_PATH.exists():
        return []

    records: List[Dict[str, Any]] = []
    with SURVEY_RESPONSES_PATH.open("r", encoding="utf-8") as handle:
        for line in handle:
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(record, dict):
                records.append(record)
    return records


@app.get("/")
def root():
    return {"status": "Cognitive Adaptive AI Tutor API running"}


@app.get("/student/state")
def get_state():
    state = get_student_state()
    macro = state.get("macro_decision", {}) or {}
    macro_with_action = macro.copy()
    if "action" not in macro_with_action and "macro_action" in macro_with_action:
        macro_with_action["action"] = macro_with_action.get("macro_action")

    return {
        "student_id": state.get("student_id"),
        "name": state.get("name"),
        "subject": state.get("subject", "python_general"),
        "level": state.get("level", "beginner"),
        "engagement": state.get("engagement", "medium"),
        "last_score": state.get("last_score", 0.0),
        "current_topic": state.get("current_topic"),
        "current_subtopic": state.get("current_subtopic"),
        "macro_decision": macro_with_action,
        "learning_gain_history": state.get("learning_gain_history", []),
        "learning_gain": state.get("learning_gain", 0.0),
        "normalized_learning_gain": state.get("normalized_learning_gain", 0.0),
        "pretest_score": state.get("pretest_score"),
        "posttest_score": state.get("posttest_score"),
        "assessment_scores": state.get("assessment_scores", {}),
        "assessment_history": state.get("assessment_history", []),
        "last_assessment_type": state.get("last_assessment_type"),
        "accuracy_history": state.get("accuracy_history", []),
        "knowledge_state": state.get("knowledge_state", {}),
        "subtopic_mastery": state.get("subtopic_mastery", {}),
        "subtopic_progress": state.get("subtopic_progress", {}),
    }


@app.get("/student/topics")
def get_topics():
    state = get_student_state()
    knowledge_state = state.get("knowledge_state", {})

    topics = []
    concepts = knowledge_state.get("concepts", {})

    for topic_name, data in concepts.items():
        if isinstance(data, dict):
            topics.append(
                {
                    "name": topic_name,
                    "mastery": data.get("mastery", 0.0),
                    "confidence": data.get("confidence", 0.0),
                    "attempts": data.get("attempts", 0),
                    "weak_areas": data.get("weak_areas", []),
                }
            )

    return {"topics": topics}


@app.post("/study/survey")
def submit_study_survey(body: StudySurveyRequest):
    state = get_student_state()
    responses = _validated_survey_scores(body.responses)
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "student_id": body.student_id or state.get("student_id", STUDENT_ID),
        "topic": body.topic or state.get("current_topic"),
        "subtopic": body.subtopic or state.get("current_subtopic"),
        "responses": responses,
        "open_text": {
            "liked_most": body.liked_most or "",
            "improve": body.improve or "",
        },
    }
    _append_survey_response(payload)
    return {
        "status": "stored",
        "response_count": len(responses),
        "path": str(SURVEY_RESPONSES_PATH),
    }


@app.get("/study/results")
def get_study_results():
    records = _read_survey_responses()
    rows = []
    for question in SURVEY_QUESTIONS:
        values = []
        for record in records:
            responses = record.get("responses", {})
            value = responses.get(question["id"]) if isinstance(responses, dict) else None
            if isinstance(value, (int, float)):
                values.append(float(value))
        rows.append(
            {
                "question_id": question["id"],
                "section": question["section"],
                "question": question["question"],
                "mean": round(sum(values) / len(values), 4) if values else None,
                "count": len(values),
            }
        )

    return {
        "table": "Table 2",
        "response_count": len(records),
        "questions": rows,
    }


@app.post("/tutor/explain")
def get_explanation(body: TopicRequest):
    state = get_student_state()
    state["current_topic"] = body.topic
    if body.subtopic:
        state["current_subtopic"] = body.subtopic
    trace_payload = {
        "phase": "pre_macro_decision",
        "node": "topic_selection",
        "current_topic": state.get("current_topic"),
        "current_subtopic": state.get("current_subtopic"),
        "student_state": state,
    }
    from core.logging_utils import trace_event
    trace_event("state_topic_updated", trace_payload)
    rag_status = _ensure_rag_ready()

    flow = _run_adaptive_learning_flow(state, rag_status=rag_status)
    macro = flow["macro"]
    validated = flow["validated"]
    updated_state = flow["updated_state"]
    rag_chunk_records = validated.get("rag_chunk_records", []) or []
    append_delivered_chunks(updated_state, body.topic, rag_chunk_records)
    next_recommendation = build_next_recommendation(updated_state, body.topic)
    pm.save(STUDENT_ID, updated_state)

    return {
        "topic": body.topic,
        "learning_path": validated.get("learning_path", ""),
        "rag_chunks": validated.get("rag_chunks", []),
        "teacher_style": validated.get("teacher_style", ""),
        "macro_decision": {
            "action": macro.get("macro_action", ""),
            "reason": _format_macro_reason(macro),
        },
        "model_used": "gemini/Groq-fallback via ModelRouterAgent",
        "proposal_id": validated.get("proposal_id"),
        "validation_status": validated.get("validation_status"),
        "next_recommendation": next_recommendation,
    }


@app.get("/tutor/explain/stream")
async def stream_explanation(topic: str, subtopic: str | None = None):
    async def event_generator():
        try:
            state = get_student_state()
            state["current_topic"] = topic
            if subtopic:
                state["current_subtopic"] = subtopic
            from core.logging_utils import trace_event
            trace_event(
                "state_topic_updated",
                {
                    "phase": "pre_macro_decision",
                    "node": "topic_selection_stream",
                    "current_topic": state.get("current_topic"),
                    "current_subtopic": state.get("current_subtopic"),
                    "student_state": state,
                },
            )
            rag_status = _ensure_rag_ready()

            flow = _run_adaptive_learning_flow(state, rag_status=rag_status)
            macro = flow["macro"]
            validated = flow["validated"]
            updated_state = flow["updated_state"]

            rag_chunk_records = validated.get("rag_chunk_records", []) or []
            append_delivered_chunks(updated_state, topic, rag_chunk_records)
            next_recommendation = build_next_recommendation(updated_state, topic)
            pm.save(STUDENT_ID, updated_state)

            learning_path = validated.get("learning_path", "")
            payload = {
                "topic": topic,
                "subtopic": state.get("current_subtopic"),
                "rag_chunks": validated.get("rag_chunks", []),
                "teacher_style": validated.get("teacher_style", ""),
                "macro_decision": {
                    "action": macro.get("macro_action", ""),
                    "reason": _format_macro_reason(macro),
                },
                "model_used": "gemini/Groq-fallback via ModelRouterAgent",
                "proposal_id": validated.get("proposal_id"),
                "validation_status": validated.get("validation_status"),
                "next_recommendation": next_recommendation,
            }
            chunk_size = 18
            for i in range(0, len(learning_path), chunk_size):
                yield _sse_delta(learning_path[i : i + chunk_size], meta=payload if i == 0 else None)
                await asyncio.sleep(0.03)
            yield _sse_delta("", done=True)
        except Exception as exc:
            yield _sse_delta(f"\n\nError: {str(exc)}", done=True)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/quiz/generate")
def get_quiz(body: TopicRequest):
    state = get_student_state()
    state["current_topic"] = body.topic
    if body.subtopic:
        state["current_subtopic"] = body.subtopic
    current_subtopic = str(state.get("current_subtopic") or f"{body.topic}_introduction")
    state["current_subtopic"] = current_subtopic
    _reset_seen_hashes_for_other_subtopics(state, body.topic, current_subtopic)
    seen_hashes = _get_seen_hashes_for_subtopic(state, body.topic, current_subtopic)
    subject = str(state.get("subject", "python_general"))
    _ensure_rag_ready()

    macro = decision_engine.decide_macro_plan(state)
    state["macro_decision"] = macro
    micro = decision_engine.decide_next_step(state)

    engineered_query = crew.tutor.query_engineer.engineer(
        f"Quiz questions for {body.topic}",
        state,
    )
    delivered_summary = get_delivered_topic_summary(state, body.topic)
    delivered_chunk_ids = delivered_summary.get("chunk_ids", [])
    delivered_concepts = delivered_summary.get("concepts", [])

    rag_chunk_records: List[Dict[str, Any]] = []
    retrieval_warning = ""
    try:
        if "dsa" in subject.lower():
            if delivered_chunk_ids:
                # Restrict quiz retrieval to already-delivered chunk ids.
                rag_chunk_records = crew.tutor.retrieve_context_chunk_records(
                    engineered_query,
                    state,
                    k=2,
                    allowed_chunk_ids=delivered_chunk_ids,
                )
        else:
            rag_chunk_records = crew.tutor.retrieve_context_chunk_records(engineered_query, state, k=2)
    except Exception as exc:
        retrieval_warning = f"RAG retrieval fallback used: {exc}"
        rag_chunk_records = []

    rag_chunks = [
        str(item.get("content", "")).strip()
        for item in rag_chunk_records
        if str(item.get("content", "")).strip()
    ]
    quiz_basis = {
        "topics_covered": [body.topic] if delivered_chunk_ids else [],
        "concepts_covered": delivered_concepts,
        "chunk_ids_used": [str(item.get("chunk_id", "")) for item in rag_chunk_records if str(item.get("chunk_id", ""))],
    }
    domain_fallback = "DSA fundamentals" if "dsa" in subject.lower() else "Python programming fundamentals"
    rag_context = "\n\n".join(rag_chunks) if rag_chunks else domain_fallback
    questions = crew.practical.generate_quiz_batch(
        micro,
        state,
        rag_context,
        target_count=6,
        seen_hashes=seen_hashes,
    )
    if len(questions) < 6:
        extra_questions = crew.practical.generate_quiz_batch(
            micro,
            state,
            rag_context,
            target_count=6 - len(questions),
            seen_hashes=seen_hashes,
        )
        questions = questions + extra_questions
    _store_seen_hashes_for_subtopic(
        state,
        body.topic,
        current_subtopic,
        seen_hashes.union({_question_hash(q.get("question", "")) for q in questions if isinstance(q, dict)}),
    )
    pm.save(STUDENT_ID, state)
    validated_questions: List[Dict[str, Any]] = []
    for q in questions:
        try:
            validated_questions.append(QuizQuestion.model_validate(q).model_dump())
        except Exception:
            continue

    return {
        "topic": body.topic,
        "subtopic": state.get("current_subtopic"),
        "questions": validated_questions,
        "rag_grounded": bool(rag_chunks),
        "quiz_basis": quiz_basis,
        "retrieval_warning": retrieval_warning,
    }


def _normalize_answer(value: str) -> str:
    return " ".join(str(value or "").strip().lower().split())


def _resolve_option_match(selected: str, correct: str, options: List[str] | None = None) -> bool:
    if _normalize_answer(selected) == _normalize_answer(correct):
        return True
    if options:
        norm_options = {_normalize_answer(opt): opt for opt in options}
        selected_norm = _normalize_answer(selected)
        correct_norm = _normalize_answer(correct)
        if selected_norm in norm_options and correct_norm in norm_options:
            return selected_norm == correct_norm
        close = get_close_matches(correct_norm, list(norm_options.keys()), n=1, cutoff=0.45)
        if close:
            return selected_norm == close[0]
    return False


def _score_answer_batch(answers: List[QuizBatchAnswer]) -> tuple[int, int, float]:
    total = max(1, len(answers))
    correct_count = 0
    for answer in answers:
        if _resolve_option_match(answer.selected_answer, answer.correct_answer):
            correct_count += 1
    return correct_count, total, round(correct_count / total, 4)


def _generate_assessment_questions(state: Dict[str, Any], topic: str, subtopic: str, assessment_type: str) -> Dict[str, Any]:
    state["current_topic"] = topic
    state["current_subtopic"] = subtopic
    state["last_assessment_type"] = assessment_type
    subject = str(state.get("subject", "python_general"))
    _ensure_rag_ready()

    macro = decision_engine.decide_macro_plan(state)
    state["macro_decision"] = macro
    micro = decision_engine.decide_next_step(state)

    engineered_query = crew.tutor.query_engineer.engineer(
        f"{assessment_type} diagnostic quiz questions for {topic} {subtopic}",
        state,
    )
    delivered_summary = get_delivered_topic_summary(state, topic)
    delivered_chunk_ids = delivered_summary.get("chunk_ids", [])

    rag_chunk_records: List[Dict[str, Any]] = []
    retrieval_warning = ""
    try:
        if "dsa" in subject.lower() and delivered_chunk_ids:
            rag_chunk_records = crew.tutor.retrieve_context_chunk_records(
                engineered_query,
                state,
                k=2,
                allowed_chunk_ids=delivered_chunk_ids,
            )
        elif "dsa" not in subject.lower():
            rag_chunk_records = crew.tutor.retrieve_context_chunk_records(engineered_query, state, k=2)
    except Exception as exc:
        retrieval_warning = f"RAG retrieval fallback used: {exc}"
        rag_chunk_records = []

    rag_chunks = [
        str(item.get("content", "")).strip()
        for item in rag_chunk_records
        if str(item.get("content", "")).strip()
    ]
    domain_fallback = "DSA fundamentals" if "dsa" in subject.lower() else "Python programming fundamentals"
    rag_context = "\n\n".join(rag_chunks) if rag_chunks else domain_fallback
    questions = crew.practical.generate_quiz_batch(
        micro,
        state,
        rag_context,
        target_count=6,
        seen_hashes=set(),
    )
    if len(questions) < 6:
        questions.extend(
            crew.practical.generate_quiz_batch(
                micro,
                state,
                rag_context,
                target_count=6 - len(questions),
                seen_hashes={_question_hash(q.get("question", "")) for q in questions if isinstance(q, dict)},
            )
        )

    validated_questions: List[Dict[str, Any]] = []
    for question in questions:
        try:
            validated_questions.append(QuizQuestion.model_validate(question).model_dump())
        except Exception:
            continue

    return {
        "type": assessment_type,
        "topic": topic,
        "subtopic": subtopic,
        "questions": validated_questions,
        "rag_grounded": bool(rag_chunks),
        "retrieval_warning": retrieval_warning,
    }


def _handle_assessment(body: AssessmentRequest, assessment_type: str) -> Dict[str, Any]:
    state = get_student_state()
    subtopic = body.subtopic or state.get("current_subtopic") or f"{body.topic}_assessment"

    if body.answers is None:
        state["current_topic"] = body.topic
        state["current_subtopic"] = subtopic
        state["last_assessment_type"] = assessment_type
        pm.save(STUDENT_ID, state)
        return _generate_assessment_questions(state, body.topic, subtopic, assessment_type)

    correct_count, total, score = _score_answer_batch(body.answers)
    state["current_topic"] = body.topic
    state["current_subtopic"] = subtopic
    state["last_score"] = score
    state.setdefault("learning_history", []).append(
        {
            "type": assessment_type,
            "topic": body.topic,
            "subtopic": subtopic,
            "score": score,
            "question_count": total,
        }
    )
    state = record_assessment_score(state, body.topic, subtopic, assessment_type, score)
    pm.save(STUDENT_ID, state)

    assessment_entry = (
        state.get("assessment_scores", {})
        .get(body.topic, {})
        .get(subtopic, {})
    )
    return {
        "type": assessment_type,
        "topic": body.topic,
        "subtopic": subtopic,
        "correct_count": correct_count,
        "total_questions": total,
        "score": score,
        "pretest_score": assessment_entry.get("pretest_score", state.get("pretest_score")),
        "posttest_score": assessment_entry.get("posttest_score", state.get("posttest_score")),
        "learning_gain": assessment_entry.get("learning_gain", state.get("learning_gain", 0.0)),
        "normalized_learning_gain": assessment_entry.get(
            "normalized_learning_gain",
            state.get("normalized_learning_gain", 0.0),
        ),
    }


@app.post("/quiz/pretest")
def pretest_quiz(body: AssessmentRequest):
    return _handle_assessment(body, "pretest")


@app.post("/quiz/posttest")
def posttest_quiz(body: AssessmentRequest):
    return _handle_assessment(body, "posttest")


@app.post("/quiz/submit")
def submit_answer(body: QuizBatchSubmitRequest):
    state = get_student_state()
    state["current_topic"] = body.topic
    state["current_subtopic"] = body.subtopic

    total = max(1, len(body.answers))
    correct_count = 0
    for answer in body.answers:
        if _resolve_option_match(answer.selected_answer, answer.correct_answer):
            correct_count += 1
    score = round(correct_count / total, 4)

    state["last_score"] = score
    state.setdefault("learning_history", []).append(
        {
            "topic": body.topic,
            "subtopic": body.subtopic,
            "score": score,
            "question_count": total,
        }
    )
    subtopic_mastery = state.setdefault("subtopic_mastery", {})
    subtopic_mastery[body.subtopic] = score
    subtopic_progress = state.setdefault("subtopic_progress", {})
    subtopic_progress[body.subtopic] = {
        "score": score,
        "passed": score >= UNLOCK_THRESHOLD,
        "attempts": int(subtopic_progress.get(body.subtopic, {}).get("attempts", 0)) + 1 if isinstance(subtopic_progress.get(body.subtopic), dict) else 1,
    }

    updated_state = simulation.run_cycle(state)
    updated_state = apply_execution_feedback(
        updated_state,
        {
            "topic": body.topic,
            "observed_score": score,
            "observed_engagement": updated_state.get("engagement"),
        },
        updated_state.get("macro_decision", {}),
    )

    pm.save(STUDENT_ID, updated_state)

    return {
        "correct": score >= UNLOCK_THRESHOLD,
        "correct_count": correct_count,
        "total_questions": total,
        "score": score,
        "passed_threshold": score >= UNLOCK_THRESHOLD,
        "unlock_threshold": UNLOCK_THRESHOLD,
        "updated_level": updated_state.get("level"),
        "updated_engagement": updated_state.get("engagement"),
        "updated_macro_decision": updated_state.get("macro_decision", {}),
        "knowledge_state": updated_state.get("knowledge_state", {}),
    }


@app.post("/curriculum/next")
def curriculum_next(body: CurriculumNextRequest):
    next_subtopic, topic_complete = get_next_subtopic(body.current_topic, body.current_subtopic)
    return {
        "next_subtopic": next_subtopic,
        "topic_complete": topic_complete,
    }
