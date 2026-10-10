"""
api_server.py  —  Cognitive Adaptive AI Tutor
==============================================

Root-cause fixes in this version
──────────────────────────────────
Issue #1  Adaptive learning not working:
  /tutor/explain/stream now passes the up-to-date student state (including
  last_score, knowledge_state, weak_areas) through _run_adaptive_learning_flow
  which feeds into TutorAgent.generate_learning_path → adaptive_engine.
  Quiz submission via /quiz/submit calls adaptive_engine.after_quiz_submit
  to update mastery/scaffold_level before the next explanation is generated.

Issue #2  Content repetition:
  record_content() from adaptive_engine is called after every explanation so
  the "prior content" anti-repetition guard activates on the next call.

Issue #3  Quiz repetition:
  /quiz/generate tracks seen question hashes per subtopic in student state,
  passes them to generate_quiz_batch, and persists after each call.

Issue #4  Quiz rendered below content:
  /tutor/explain/stream no longer includes quiz in its response payload.
  /quiz/generate is a separate, explicit endpoint.

Issue #5  Only one topic shown:
  /student/topics now uses get_all_curriculum_topics() from curriculum_config
  so all 7 DSA topics (array, linked_list, stack, queue, hash_table, tree,
  graph) are returned with their subtopic lists.

Issue #6  Source material not utilised:
  No change to RAG plumbing needed — the adaptive prompts in tutor_agent and
  practical_agent now inject the RAG context more forcefully.

Issue #7  Learning state not maintained:
  /quiz/submit calls after_quiz_submit() which calls record_quiz_attempt() in
  adaptive_learning.py — this updates mastery, confidence, scaffold_level,
  weak_areas, strong_areas, and level persistently in the student profile.
"""

from fastapi import FastAPI, HTTPException, Depends, Header
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
from typing import Any, Dict, List, Optional
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
from core.curriculum_config import UNLOCK_THRESHOLD, get_next_subtopic, get_all_curriculum_topics
from core.practical_agent import QuizQuestion
from core.logging_utils import Timer, get_logger
from core.metrics_collector import log_learning_cycle_metrics
from core.adaptive_engine import after_quiz_submit, record_content, get_all_topics
from core.question_bank_service import get_question_bank_service, DEFAULT_QUIZ_LENGTH

app = FastAPI(title="Cognitive Adaptive AI Tutor API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://cognitive-adaptive-ai-tutor.vercel.app",
        "https://cognitive-adaptive-ai-tutor-git-deploy1-msui.vercel.app",
    ],
    allow_credentials=True,
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
logger = get_logger("api_server", "api_server.log")

# ── Authentication ────────────────────────────────────────────────────────────
from core.auth import AuthManager
auth_manager = AuthManager()

# Legacy fallback student ID (used only when no auth token is present)
# in non-protected diagnostic/health endpoints.
STUDENT_ID = "KISH-001"


def _derive_student_id(user_id: str) -> str:
    """Convert a Supabase UUID into a short student profile ID."""
    return f"USER-{user_id[:8]}"


def require_auth(authorization: str = Header(None)) -> Dict[str, Any]:
    """
    FastAPI dependency — validates Bearer token and returns user dict.
    Inject with: user: Dict = Depends(require_auth)
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Please login first.",
        )
    token = authorization.replace("Bearer ", "", 1).strip()
    user = auth_manager.verify_token(token)
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token. Please login again.",
        )
    user["student_id"] = _derive_student_id(user["user_id"])
    return user


def _get_student_state_for(student_id: str) -> dict:
    """Load student state for a given student_id, creating profile if needed."""
    try:
        return pm.load(student_id)
    except FileNotFoundError:
        return {
            "student_id": student_id,
            "name": "Student",
            "subject": "dsa",
            "level": "beginner",
            "current_topic": "array",
            "progress": [],
            "engagement": "medium",
            "last_score": 0.3,
            "learning_history": [],
            "knowledge_state": {
                "concepts": {
                    "array": {
                        "mastery": 0.2,
                        "confidence": 0.25,
                        "attempts": 0,
                        "scaffold_level": "high",
                        "weak_areas": [],
                        "strong_areas": [],
                        "completed": False,
                    }
                },
                "version": 2,
            },
            "delivered_chunks": {},
            "quiz_seen_questions": {},
            "weak_areas": {},
            "strong_areas": {},
            "quiz_attempts": {},
            "generated_content_history": {},
            "content_fingerprints": {},
        }
SURVEY_RESPONSES_PATH = Path("data/survey_responses.jsonl")
SURVEY_QUESTIONS: List[Dict[str, str]] = [
    {"id": "usability_easy_to_use",      "section": "Usability",   "question": "The system was easy to use"},
    {"id": "usability_clear_explanations","section": "Usability",   "question": "The explanations were clear and understandable"},
    {"id": "usability_quiz_alignment",    "section": "Usability",   "question": "The quizzes matched what I just learned"},
    {"id": "usability_adapted_level",     "section": "Usability",   "question": "The system felt like it adapted to my level"},
    {"id": "usability_use_again",         "section": "Usability",   "question": "I would use this system again to learn a new topic"},
    {"id": "trust_explanations",          "section": "Trust",       "question": "I trusted the system's explanations"},
    {"id": "trust_hints",                 "section": "Trust",       "question": "The system gave me appropriate hints"},
    {"id": "trust_learning_needs",        "section": "Trust",       "question": "I felt the system understood my learning needs"},
    {"id": "engagement_throughout",       "section": "Engagement",  "question": "I was engaged throughout the session"},
    {"id": "engagement_difficulty",       "section": "Engagement",  "question": "The difficulty felt appropriate for me"},
    {"id": "engagement_progress",         "section": "Engagement",  "question": "I felt I made progress"},
]

from core.teacher_review_agent import TeacherReviewAgent
original_review = TeacherReviewAgent.review


def auto_approve_review(self, crew_output, student_state):
    return {"review_status": "approved", "comments": "auto-approved via API"}


TeacherReviewAgent.review = auto_approve_review


# ──────────────────────────────────────────────────────────────────────────────
# Student state helpers
# ──────────────────────────────────────────────────────────────────────────────

def get_student_state(student_id: str = STUDENT_ID) -> dict:
    """Load student state (defaults to legacy STUDENT_ID for backward compat)."""
    return _get_student_state_for(student_id)


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


def _reset_seen_hashes_for_other_subtopics(
    state: Dict[str, Any], topic: str, active_subtopic: str
) -> None:
    quiz_seen = state.setdefault("quiz_seen_questions", {})
    topic_map = quiz_seen.setdefault(topic, {})
    for key in list(topic_map.keys()):
        if key != active_subtopic:
            topic_map.pop(key, None)


def _ensure_rag_ready() -> Dict[str, Any]:
    try:
        return file_manager.prepare_knowledge_base(force_reingest=False)
    except Exception as exc:
        return {"rag_ready": False, "status": "failed", "detail": str(exc)}


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
        fallback.append({
            "question": q_text,
            "options": options,
            "correct_answer": correct,
            "explanation": f"This option correctly captures the purpose of {topic}.",
            "hint": f"Focus on how {topic} is used in real learning tasks.",
        })
    return fallback


def _run_adaptive_learning_flow(
    state: Dict[str, Any],
    rag_status: Dict[str, Any] | None = None,
    quiz_pass_rate: float | None = None,
    user_id: str | None = None,
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
    
    # Extract RAG latency - try multiple sources
    rag_latency_ms = validated.get("rag_latency_ms", 0.0)
    if rag_latency_ms == 0.0:
        rag_latency_ms = (rag_status or {}).get("duration_ms", 0.0)
    
    log_learning_cycle_metrics(
        student_state=updated_state,
        macro_decision=macro,
        micro_decision=decision,
        crew_output=validated,
        timings={
            "rag_latency_ms": rag_latency_ms,
            "crewai_latency_ms": crew_ms,
            "e2e_latency_ms": round(e2e_timer.elapsed_ms(), 2),
        },
        rag_chunk_records=rag_chunk_records,
        decision_iterations=1,
        quiz_pass_rate=quiz_pass_rate,
    )
    pm.save(updated_state.get("student_id", STUDENT_ID), updated_state, user_id=user_id)
    return {
        "macro": macro,
        "decision": decision,
        "validated": validated,
        "monitor_output": monitor_out,
        "updated_state": updated_state,
    }


# ──────────────────────────────────────────────────────────────────────────────
# Request/Response models
# ──────────────────────────────────────────────────────────────────────────────

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


# ──────────────────────────────────────────────────────────────────────────────
# SSE helpers
# ──────────────────────────────────────────────────────────────────────────────

def _sse_delta(delta: str, done: bool = False, meta: Dict[str, Any] | None = None) -> str:
    payload: Dict[str, Any] = {"delta": delta}
    if done:
        payload["done"] = True
    if meta:
        payload["meta"] = meta
    return f"data: {json.dumps(payload)}\n\n"


# ──────────────────────────────────────────────────────────────────────────────
# Survey helpers
# ──────────────────────────────────────────────────────────────────────────────

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


# ──────────────────────────────────────────────────────────────────────────────
# Answer scoring helpers
# ──────────────────────────────────────────────────────────────────────────────

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


# ──────────────────────────────────────────────────────────────────────────────
# Authentication Request/Response Models
# ──────────────────────────────────────────────────────────────────────────────

class SignupRequest(BaseModel):
    email: str
    password: str
    name: Optional[str] = None


class LoginRequest(BaseModel):
    email: str
    password: str


class LogoutRequest(BaseModel):
    token: str


class PasswordResetRequest(BaseModel):
    email: str


# ──────────────────────────────────────────────────────────────────────────────
# Authentication Endpoints
# ──────────────────────────────────────────────────────────────────────────────

@app.post("/auth/signup")
async def auth_signup(request: SignupRequest):
    """Create a new user account and initialise student profile."""
    result = auth_manager.signup(
        email=request.email,
        password=request.password,
        name=request.name,
    )
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])

    user_id = result["user_id"]
    student_id = _derive_student_id(user_id)
    name = request.name or request.email.split("@")[0]

    # Create the student profile JSON if it does not already exist.
    if student_id not in pm.list_profiles():
        pm.create_profile(
            student_id=student_id,
            name=name,
            level="beginner",
            learning_style="balanced",
            user_id=user_id,
        )
    else:
        # Profile already exists — still push its data to Supabase
        existing = pm.load(student_id)
        pm.save(student_id, existing, user_id=user_id)

    result["student_id"] = student_id
    result["name"] = name
    return result


@app.post("/auth/login")
async def auth_login(request: LoginRequest):
    """Authenticate an existing user and return a JWT token."""
    result = auth_manager.login(
        email=request.email,
        password=request.password,
    )
    if not result["success"]:
        raise HTTPException(status_code=401, detail=result["error"])

    user_id = result["user_id"]
    student_id = _derive_student_id(user_id)
    result["student_id"] = student_id

    # Ensure profile exists (first login after manual signup, etc.)
    if student_id not in pm.list_profiles():
        pm.create_profile(
            student_id=student_id,
            name=result.get("name", request.email.split("@")[0]),
            level="beginner",
            learning_style="balanced",
            user_id=user_id,
        )
    else:
        # Profile exists — sync it to Supabase on every login
        existing = pm.load(student_id)
        pm.save(student_id, existing, user_id=user_id)

    return result


@app.post("/auth/logout")
async def auth_logout(request: LogoutRequest):
    """Invalidate a user session."""
    result = auth_manager.logout(request.token)
    return result


@app.get("/auth/me")
async def auth_me(user: Dict = Depends(require_auth)):
    """Return info about the currently authenticated user."""
    return {
        "user_id": user["user_id"],
        "email": user["email"],
        "name": user.get("name"),
        "student_id": user["student_id"],
    }


@app.post("/auth/reset-password")
async def auth_reset_password(request: PasswordResetRequest):
    """Send a password reset email."""
    result = auth_manager.reset_password_request(request.email)
    # Always return success to avoid email enumeration.
    return {"success": True, "message": "If that email exists, a reset link has been sent."}


# ──────────────────────────────────────────────────────────────────────────────
# Routes
# ──────────────────────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return {"status": "Cognitive Adaptive AI Tutor API running", "version": "2.0.0"}


@app.get("/student/state")
def get_state(user: Dict = Depends(require_auth)):
    student_id = user["student_id"]
    state = get_student_state(student_id)
    macro = state.get("macro_decision", {}) or {}
    macro_with_action = macro.copy()
    if "action" not in macro_with_action and "macro_action" in macro_with_action:
        macro_with_action["action"] = macro_with_action.get("macro_action")

    return {
        "student_id": state.get("student_id"),
        "name": state.get("name") or user.get("name"),
        "subject": state.get("subject", "dsa"),
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
        "weak_areas": state.get("weak_areas", {}),
        "strong_areas": state.get("strong_areas", {}),
        "quiz_attempts": state.get("quiz_attempts", {}),
        "completed_topics": state.get("completed_topics", []),
    }


@app.get("/student/topics")
def get_topics(user: Dict = Depends(require_auth)):
    """
    Issue #5 fix: returns ALL curriculum topics (not just the ones that happen
    to be in the student's knowledge_state) together with subtopic lists so the
    sidebar can render a complete, navigable topic tree.
    """
    state = get_student_state(user["student_id"])
    knowledge_state = state.get("knowledge_state", {})
    concepts = knowledge_state.get("concepts", {})
    subtopic_progress = state.get("subtopic_progress", {})
    subtopic_mastery = state.get("subtopic_mastery", {})

    # Full curriculum from curriculum_config (all 7 DSA topics).
    curriculum = get_all_curriculum_topics()

    topics = []
    for topic_def in curriculum:
        name = topic_def["name"]
        concept_data = concepts.get(name, {})
        subtopic_details = topic_def.get("subtopic_details", [])

        # Enrich each subtopic with progress data.
        enriched_subtopics = []
        for sub in subtopic_details:
            sid = sub["id"]
            prog = subtopic_progress.get(sid, {})
            enriched_subtopics.append({
                "id": sid,
                "title": sub["title"],
                "score": subtopic_mastery.get(sid, 0.0),
                "passed": bool(prog.get("passed", False)),
                "attempts": int(prog.get("attempts", 0)),
            })

        topics.append({
            "name": name,
            "mastery": float(concept_data.get("mastery", 0.0)),
            "confidence": float(concept_data.get("confidence", 0.0)),
            "attempts": int(concept_data.get("attempts", 0)),
            "scaffold_level": str(concept_data.get("scaffold_level", "high")),
            "weak_areas": concept_data.get("weak_areas", []),
            "strong_areas": concept_data.get("strong_areas", []),
            "completed": bool(concept_data.get("completed", False)),
            "subtopics": enriched_subtopics,
        })

    return {"topics": topics}


@app.get("/curriculum/topics")
def get_curriculum_topics(user: Dict = Depends(require_auth)):
    """Full curriculum definition without per-student enrichment."""
    return {"topics": get_all_curriculum_topics()}


@app.post("/study/survey")
def submit_study_survey(body: StudySurveyRequest, user: Dict = Depends(require_auth)):
    student_id = user["student_id"]
    state = get_student_state(student_id)
    responses = _validated_survey_scores(body.responses)
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "student_id": student_id,
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
        rows.append({
            "question_id": question["id"],
            "section": question["section"],
            "question": question["question"],
            "mean": round(sum(values) / len(values), 4) if values else None,
            "count": len(values),
        })
    return {
        "table": "Table 2",
        "response_count": len(records),
        "questions": rows,
    }


@app.post("/tutor/explain")
def get_explanation(body: TopicRequest, user: Dict = Depends(require_auth)):
    student_id = user["student_id"]
    state = get_student_state(student_id)
    state["current_topic"] = body.topic
    if body.subtopic:
        state["current_subtopic"] = body.subtopic
    from core.logging_utils import trace_event
    trace_event("state_topic_updated", {
        "phase": "pre_macro_decision",
        "node": "topic_selection",
        "current_topic": state.get("current_topic"),
        "current_subtopic": state.get("current_subtopic"),
        "last_score": state.get("last_score"),
    })
    rag_status = _ensure_rag_ready()

    flow = _run_adaptive_learning_flow(state, rag_status=rag_status, user_id=user["user_id"])
    macro = flow["macro"]
    validated = flow["validated"]
    updated_state = flow["updated_state"]
    rag_chunk_records = validated.get("rag_chunk_records", []) or []
    append_delivered_chunks(updated_state, body.topic, rag_chunk_records)

    # -- Issue #2 fix: record the content so anti-repetition guard fires ------
    learning_path = validated.get("learning_path", "")
    if learning_path and body.subtopic:
        record_content(updated_state, body.topic, body.subtopic, learning_path)

    next_recommendation = build_next_recommendation(updated_state, body.topic)
    pm.save(student_id, updated_state, user_id=user["user_id"])

    return {
        "topic": body.topic,
        "learning_path": learning_path,
        "rag_chunks": validated.get("rag_chunks", []),
        "teacher_style": validated.get("teacher_style", ""),
        "macro_decision": {
            "action": macro.get("macro_action", ""),
            "reason": _format_macro_reason(macro),
        },
        "adaptive_mode": validated.get("adaptive_ctx", {}).get("mode", "guided"),
        "model_used": "gemini/Groq-fallback via ModelRouterAgent",
        "proposal_id": validated.get("proposal_id"),
        "validation_status": validated.get("validation_status"),
        "next_recommendation": next_recommendation,
    }


@app.get("/tutor/explain/stream")
async def stream_explanation(
    topic: str,
    subtopic: str | None = None,
    authorization: str = Header(None),
    token: str | None = None,          # fallback for browsers using EventSource
):
    """
    Issue #1 fix: state is loaded fresh on every call so the latest
    last_score/mastery feed into the adaptive prompt.
    Issue #4 fix: this endpoint returns ONLY learning content — no quiz.
    SSE endpoints cannot use Depends() directly — auth is handled inline.
    EventSource in browsers cannot send custom headers, so the JWT is
    accepted as a ?token=<jwt> query param as a fallback.
    """
    # Prefer Authorization header; fall back to ?token= query param
    effective_auth = authorization or (f"Bearer {token}" if token else None)
    user = require_auth(effective_auth)
    student_id = user["student_id"]


    async def event_generator():
        try:
            state = get_student_state(student_id)
            state["current_topic"] = topic
            if subtopic:
                state["current_subtopic"] = subtopic
            from core.logging_utils import trace_event
            trace_event("state_topic_updated", {
                "phase": "pre_macro_decision",
                "node": "topic_selection_stream",
                "current_topic": state.get("current_topic"),
                "current_subtopic": state.get("current_subtopic"),
                "last_score": state.get("last_score"),
                "level": state.get("level"),
            })
            rag_status = _ensure_rag_ready()

            flow = _run_adaptive_learning_flow(state, rag_status=rag_status, user_id=user["user_id"])
            macro = flow["macro"]
            validated = flow["validated"]
            updated_state = flow["updated_state"]

            rag_chunk_records = validated.get("rag_chunk_records", []) or []
            append_delivered_chunks(updated_state, topic, rag_chunk_records)

            # Issue #2: record content so next call can vary it.
            learning_path = validated.get("learning_path", "")
            current_subtopic = subtopic or updated_state.get("current_subtopic", f"{topic}_introduction")
            if learning_path:
                record_content(updated_state, topic, current_subtopic, learning_path)

            next_recommendation = build_next_recommendation(updated_state, topic)
            pm.save(student_id, updated_state, user_id=user["user_id"])

            meta = {
                "topic": topic,
                "subtopic": updated_state.get("current_subtopic"),
                "rag_chunks": validated.get("rag_chunks", []),
                "teacher_style": validated.get("teacher_style", ""),
                "macro_decision": {
                    "action": macro.get("macro_action", ""),
                    "reason": _format_macro_reason(macro),
                },
                # Issue #1: expose adaptive mode so the UI can show it.
                "adaptive_mode": validated.get("adaptive_ctx", {}).get("mode", "guided"),
                "adaptive_score": state.get("last_score", 0.0),
                "model_used": "gemini/Groq-fallback via ModelRouterAgent",
                "proposal_id": validated.get("proposal_id"),
                "validation_status": validated.get("validation_status"),
                "next_recommendation": next_recommendation,
                # Issue #4: explicitly tell the UI no quiz is embedded.
                "quiz_embedded": False,
            }

            chunk_size = 18
            for i in range(0, len(learning_path), chunk_size):
                yield _sse_delta(learning_path[i: i + chunk_size], meta=meta if i == 0 else None)
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
def get_quiz(body: TopicRequest, user: Dict = Depends(require_auth)):
    """
    Issue #3 fix: seen question hashes are loaded, passed to the quiz
    generator, and stored back after generation so repeated calls produce
    different questions.

    Issue #4 fix: this is the ONLY place quiz questions are generated;
    the /tutor/explain/stream endpoint no longer generates them.

    Question-bank fix: tries the pre-built question bank first (adaptive
    count = min(DEFAULT_QUIZ_LENGTH, available_unseen)).  Falls back to
    LLM generation when the bank is empty or not yet ingested.
    """
    student_id = user["student_id"]
    state = get_student_state(student_id)
    state["current_topic"] = body.topic
    if body.subtopic:
        state["current_subtopic"] = body.subtopic
    current_subtopic = str(state.get("current_subtopic") or f"{body.topic}_introduction")
    state["current_subtopic"] = current_subtopic
    _reset_seen_hashes_for_other_subtopics(state, body.topic, current_subtopic)
    seen_hashes = _get_seen_hashes_for_subtopic(state, body.topic, current_subtopic)
    subject = str(state.get("subject", "dsa"))

    macro = decision_engine.decide_macro_plan(state)
    state["macro_decision"] = macro
    micro = decision_engine.decide_next_step(state)

    # ── Step 1: try the pre-built question bank ──────────────────────────────
    difficulty = str(state.get("difficulty_level") or micro.get("difficulty", "medium")).lower()
    qbs = get_question_bank_service()
    bank_result = qbs.get_quiz(
        topic=body.topic,
        difficulty=difficulty,
        pool="practice_pool",
        student_id=student_id,
        context="practice",
    )

    if bank_result is not None:
        # Bank responded (may be 0 questions if pool is totally exhausted)
        bank_questions = bank_result["questions"]
        actual = bank_result["actual_count"]
        widened = bank_result["widened_difficulty"]
        diffs_used = bank_result["difficulties_used"]

        if actual > 0:
            logger.info(
                "quiz/generate bank hit: topic=%r difficulty=%r diffs_used=%r "
                "pool=practice_pool student=%r actual=%d/%d widened=%s",
                body.topic, difficulty, diffs_used, student_id,
                actual, DEFAULT_QUIZ_LENGTH, widened,
            )
            pm.save(student_id, state, user_id=user["user_id"])
            return {
                "topic": body.topic,
                "subtopic": current_subtopic,
                "questions": bank_questions,
                "rag_grounded": False,
                "quiz_basis": {"source": "question_bank", "difficulties_used": diffs_used},
                "retrieval_warning": (
                    f"Pool thin: only {actual} of {DEFAULT_QUIZ_LENGTH} questions available"
                    + (f" (widened to {diffs_used})" if widened else "")
                    if actual < DEFAULT_QUIZ_LENGTH else ""
                ),
                "adaptive_mode": macro.get("scaffold_policy", "medium"),
                "bank_metadata": {
                    "source": "question_bank",
                    "actual_count": actual,
                    "default_count": DEFAULT_QUIZ_LENGTH,
                    "widened_difficulty": widened,
                    "difficulties_used": diffs_used,
                },
            }

        # Pool completely exhausted — note in log and fall through to LLM
        logger.warning(
            "quiz/generate bank pool exhausted: topic=%r difficulty=%r "
            "pool=practice_pool student=%r — falling back to LLM",
            body.topic, difficulty, student_id,
        )

    # ── Step 2: LLM fallback (original path) ────────────────────────────────
    _ensure_rag_ready()
    engineered_query = crew.tutor.query_engineer.engineer(
        f"Quiz questions for {body.topic} — {current_subtopic}", state
    )
    delivered_summary = get_delivered_topic_summary(state, body.topic)
    delivered_chunk_ids = delivered_summary.get("chunk_ids", [])
    delivered_concepts = delivered_summary.get("concepts", [])

    rag_chunk_records: List[Dict[str, Any]] = []
    retrieval_warning = ""
    try:
        # Use k=4 to pull more OpenDSA/textbook chunks — richer context → more unique questions.
        if "dsa" in subject.lower():
            if delivered_chunk_ids:
                rag_chunk_records = crew.tutor.retrieve_context_chunk_records(
                    engineered_query, state, k=4, allowed_chunk_ids=delivered_chunk_ids
                )
                # Top-up with unrestricted chunks if not enough
                if len(rag_chunk_records) < 3:
                    rag_chunk_records = crew.tutor.retrieve_context_chunk_records(
                        engineered_query, state, k=4
                    )
            else:
                rag_chunk_records = crew.tutor.retrieve_context_chunk_records(
                    engineered_query, state, k=4
                )
        else:
            rag_chunk_records = crew.tutor.retrieve_context_chunk_records(engineered_query, state, k=4)
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

    quiz_basis = {
        "source": "llm",
        "topics_covered": [body.topic] if delivered_chunk_ids else [],
        "concepts_covered": delivered_concepts,
        "chunk_ids_used": [str(item.get("chunk_id", "")) for item in rag_chunk_records if str(item.get("chunk_id", ""))],
    }

    questions = crew.practical.generate_quiz_batch(
        micro, state, rag_context, target_count=DEFAULT_QUIZ_LENGTH, seen_hashes=seen_hashes
    )
    if len(questions) < DEFAULT_QUIZ_LENGTH:
        extra_questions = crew.practical.generate_quiz_batch(
            micro,
            state,
            rag_context,
            target_count=DEFAULT_QUIZ_LENGTH - len(questions),
            seen_hashes=seen_hashes,
        )
        questions = questions + extra_questions

    # Issue #3: persist updated seen hashes.
    _store_seen_hashes_for_subtopic(
        state,
        body.topic,
        current_subtopic,
        seen_hashes.union({_question_hash(q.get("question", "")) for q in questions if isinstance(q, dict)}),
    )
    pm.save(student_id, state, user_id=user["user_id"])

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
        # Tell the UI which adaptive mode was used so it can show context.
        "adaptive_mode": macro.get("scaffold_policy", "medium"),
        "bank_metadata": {"source": "llm"},
    }



def _generate_assessment_questions(
    state: Dict[str, Any], topic: str, subtopic: str, assessment_type: str
) -> Dict[str, Any]:
    """
    Generate pretest or posttest questions.

    Try the pre-built question bank first (adaptive count, difficulty fallback,
    thin-pool logging).  Falls back to LLM generation when the bank is empty or
    not yet ingested so the system keeps working before full Supabase migration.

    assessment_type must be "pretest" or "posttest" — maps to the corresponding
    pool (pretest_pool / posttest_pool) in the question_bank table.
    """
    state["current_topic"] = topic
    state["current_subtopic"] = subtopic
    state["last_assessment_type"] = assessment_type
    subject = str(state.get("subject", "dsa"))
    student_id: str = state.get("student_id", "")

    macro = decision_engine.decide_macro_plan(state)
    state["macro_decision"] = macro
    micro = decision_engine.decide_next_step(state)

    # Map assessment type → pool name and asked_questions context value
    pool_map = {
        "pretest":  ("pretest_pool",  "pretest"),
        "posttest": ("posttest_pool", "posttest"),
    }
    pool, context = pool_map.get(assessment_type, ("pretest_pool", "pretest"))
    difficulty = str(state.get("difficulty_level") or micro.get("difficulty", "medium")).lower()

    # ── Step 1: try the pre-built question bank ──────────────────────────────
    if student_id:
        qbs = get_question_bank_service()
        bank_result = qbs.get_quiz(
            topic=topic,
            difficulty=difficulty,
            pool=pool,
            student_id=student_id,
            context=context,
        )
    else:
        bank_result = None  # no student_id → skip bank, go straight to LLM

    if bank_result is not None:
        bank_questions = bank_result["questions"]
        actual = bank_result["actual_count"]
        widened = bank_result["widened_difficulty"]
        diffs_used = bank_result["difficulties_used"]

        if actual > 0:
            logger.info(
                "_generate_assessment_questions bank hit: type=%r topic=%r "
                "difficulty=%r diffs_used=%r pool=%r student=%r actual=%d/%d widened=%s",
                assessment_type, topic, difficulty, diffs_used, pool,
                student_id, actual, DEFAULT_QUIZ_LENGTH, widened,
            )
            return {
                "type": assessment_type,
                "topic": topic,
                "subtopic": subtopic,
                "questions": bank_questions,
                "rag_grounded": False,
                "retrieval_warning": (
                    f"Pool thin: only {actual} of {DEFAULT_QUIZ_LENGTH} questions available"
                    + (f" (widened to {diffs_used})" if widened else "")
                    if actual < DEFAULT_QUIZ_LENGTH else ""
                ),
                "bank_metadata": {
                    "source": "question_bank",
                    "actual_count": actual,
                    "default_count": DEFAULT_QUIZ_LENGTH,
                    "widened_difficulty": widened,
                    "difficulties_used": diffs_used,
                    "pool": pool,
                },
            }

        logger.warning(
            "_generate_assessment_questions bank pool exhausted: "
            "type=%r topic=%r difficulty=%r pool=%r student=%r — falling back to LLM",
            assessment_type, topic, difficulty, pool, student_id,
        )

    # ── Step 2: LLM fallback (original path) ────────────────────────────────
    _ensure_rag_ready()
    engineered_query = crew.tutor.query_engineer.engineer(
        f"{assessment_type} diagnostic quiz questions for {topic} {subtopic}", state
    )
    delivered_summary = get_delivered_topic_summary(state, topic)
    delivered_chunk_ids = delivered_summary.get("chunk_ids", [])

    rag_chunk_records: List[Dict[str, Any]] = []
    retrieval_warning = ""
    try:
        # Use k=4 to pull more OpenDSA/textbook chunks — richer source material = more unique questions.
        if "dsa" in subject.lower() and delivered_chunk_ids:
            rag_chunk_records = crew.tutor.retrieve_context_chunk_records(
                engineered_query, state, k=4, allowed_chunk_ids=delivered_chunk_ids
            )
            # Top-up with unrestricted retrieval if delivered chunks are sparse
            if len(rag_chunk_records) < 3:
                rag_chunk_records = crew.tutor.retrieve_context_chunk_records(
                    engineered_query, state, k=4
                )
        elif "dsa" not in subject.lower():
            rag_chunk_records = crew.tutor.retrieve_context_chunk_records(engineered_query, state, k=4)
        else:
            rag_chunk_records = crew.tutor.retrieve_context_chunk_records(engineered_query, state, k=4)
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

    # Load persistent seen-hashes for this assessment type + topic + subtopic
    # so repeated pretest/posttest calls never re-ask the same questions.
    assessment_seen_key = f"{assessment_type}:{topic}:{subtopic}"
    assessment_seen_store = state.setdefault("assessment_seen_questions", {})
    seen_hashes: set[str] = {str(v) for v in assessment_seen_store.get(assessment_seen_key, [])}

    questions = crew.practical.generate_quiz_batch(
        micro, state, rag_context, target_count=DEFAULT_QUIZ_LENGTH, seen_hashes=seen_hashes
    )
    if len(questions) < DEFAULT_QUIZ_LENGTH:
        questions.extend(
            crew.practical.generate_quiz_batch(
                micro,
                state,
                rag_context,
                target_count=DEFAULT_QUIZ_LENGTH - len(questions),
                seen_hashes=seen_hashes,
            )
        )

    # Persist the newly seen hashes so future calls get fresh questions.
    seen_hashes.update(
        _question_hash(q.get("question", "")) for q in questions if isinstance(q, dict)
    )
    assessment_seen_store[assessment_seen_key] = sorted(seen_hashes)

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
        "bank_metadata": {"source": "llm"},
    }



def _handle_assessment(body: AssessmentRequest, assessment_type: str, student_id: str, user_id: str | None = None) -> Dict[str, Any]:
    state = get_student_state(student_id)
    subtopic = body.subtopic or state.get("current_subtopic") or f"{body.topic}_assessment"

    if body.answers is None:
        state["current_topic"] = body.topic
        state["current_subtopic"] = subtopic
        state["last_assessment_type"] = assessment_type
        result = _generate_assessment_questions(state, body.topic, subtopic, assessment_type)
        # Save AFTER generation so assessment_seen_questions hashes are persisted.
        pm.save(student_id, state, user_id=user_id)
        return result

    correct_count, total, score = _score_answer_batch(body.answers)
    state["current_topic"] = body.topic
    state["current_subtopic"] = subtopic
    state["last_score"] = score
    state.setdefault("learning_history", []).append({
        "type": assessment_type,
        "topic": body.topic,
        "subtopic": subtopic,
        "score": score,
        "question_count": total,
    })
    state = record_assessment_score(state, body.topic, subtopic, assessment_type, score)
    pm.save(student_id, state, user_id=user_id)

    assessment_entry = (
        state.get("assessment_scores", {}).get(body.topic, {}).get(subtopic, {})
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
            "normalized_learning_gain", state.get("normalized_learning_gain", 0.0)
        ),
    }


@app.post("/quiz/pretest")
def pretest_quiz(body: AssessmentRequest, user: Dict = Depends(require_auth)):
    return _handle_assessment(body, "pretest", user["student_id"], user_id=user["user_id"])


@app.post("/quiz/posttest")
def posttest_quiz(body: AssessmentRequest, user: Dict = Depends(require_auth)):
    return _handle_assessment(body, "posttest", user["student_id"], user_id=user["user_id"])


@app.post("/quiz/submit")
def submit_answer(body: QuizBatchSubmitRequest, user: Dict = Depends(require_auth)):
    """
    Issue #1 & #7 fix:
    • Calls after_quiz_submit() from adaptive_engine which invokes
      record_quiz_attempt() in adaptive_learning — this updates mastery,
      confidence, scaffold_level, weak_areas, strong_areas and level.
    • The NEXT call to /tutor/explain/stream will load this updated state and
      produce a properly adapted explanation.
    """
    student_id = user["student_id"]
    state = get_student_state(student_id)
    state["current_topic"] = body.topic
    state["current_subtopic"] = body.subtopic

    total = max(1, len(body.answers))
    correct_count = 0
    for answer in body.answers:
        if _resolve_option_match(answer.selected_answer, answer.correct_answer):
            correct_count += 1
    score = round(correct_count / total, 4)

    # ── Issue #1 & #7: full adaptive state update after quiz ─────────────────
    state = after_quiz_submit(
        student_state=state,
        topic=body.topic,
        subtopic=body.subtopic,
        score=score,
        answers=body.answers,
    )

    # Also update subtopic-level progress tracking.
    subtopic_mastery = state.setdefault("subtopic_mastery", {})
    subtopic_mastery[body.subtopic] = score
    subtopic_progress = state.setdefault("subtopic_progress", {})
    prev_attempts = int(subtopic_progress.get(body.subtopic, {}).get("attempts", 0)) \
        if isinstance(subtopic_progress.get(body.subtopic), dict) else 0
    subtopic_progress[body.subtopic] = {
        "score": score,
        "passed": score >= UNLOCK_THRESHOLD,
        "attempts": prev_attempts + 1,
    }

    # Apply execution feedback for macro-level state updates.
    updated_state = apply_execution_feedback(
        state,
        {
            "topic": body.topic,
            "observed_score": score,
            "observed_engagement": state.get("engagement"),
        },
        state.get("macro_decision", {}),
    )

    pm.save(student_id, updated_state, user_id=user["user_id"])
    
    # Log quiz attempt to learning_history
    try:
        from core.supabase_sync import log_quiz_attempt
        log_quiz_attempt(
            state=updated_state,
            user_id=user["user_id"],
            topic=body.topic,
            subtopic=body.subtopic,
            score=score,
            question_count=total,
            passed=(score >= UNLOCK_THRESHOLD),
            record_type="quiz"
        )
    except Exception as e:
        logger.warning(f"Failed to log quiz attempt to Supabase: {e}")

    # Determine adaptive recommendation for the UI.
    concepts = updated_state.get("knowledge_state", {}).get("concepts", {})
    topic_concept = concepts.get(body.topic, {})
    new_mastery = float(topic_concept.get("mastery", score))
    scaffold_level = str(topic_concept.get("scaffold_level", "medium"))

    if score < 0.45:
        adaptive_action = "remediate"
        adaptive_message = (
            "Score was low. The next explanation will be simplified with "
            "analogies and smaller concept chunks."
        )
    elif score >= 0.75:
        adaptive_action = "advance"
        adaptive_message = (
            "Excellent score! The next explanation will increase in depth "
            "and introduce more challenging concepts."
        )
    else:
        adaptive_action = "continue"
        adaptive_message = "Good progress. Continue with the next subtopic."

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
        # Issue #1: expose the adaptive recommendation so the UI can react.
        "adaptive_action": adaptive_action,
        "adaptive_message": adaptive_message,
        "new_mastery": round(new_mastery, 4),
        "scaffold_level": scaffold_level,
        "weak_areas": updated_state.get("weak_areas", {}),
    }


@app.post("/curriculum/next")
def curriculum_next(body: CurriculumNextRequest, user: Dict = Depends(require_auth)):
    next_subtopic, topic_complete = get_next_subtopic(body.current_topic, body.current_subtopic)
    return {
        "next_subtopic": next_subtopic,
        "topic_complete": topic_complete,
    }
