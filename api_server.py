from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
import os
import json
from typing import Any, Dict, List

load_dotenv()

from core.simulation import AdaptiveLearningSimulation
from core.profile_manager import ProfileManager
from core.decision_engine import DecisionEngine
from core.education_crew import EducationCrew
from core.file_manager_agent import FileManagerAgent
from core.monitor_agent import MonitorAgent
from core.validation_agent import ValidationAgent
from core.knowledge_state_updater import apply_execution_feedback
from core.delivery_tracker import append_delivered_chunks, get_delivered_topic_summary
from core.learning_navigation import build_next_recommendation

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
        }


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


def _run_adaptive_learning_flow(state: Dict[str, Any]) -> Dict[str, Any]:
    macro = decision_engine.decide_macro_plan(state)
    state["macro_decision"] = macro
    decision = decision_engine.decide_next_step(state)
    state["decision"] = decision

    if decision.get("next_node") == "education_crew":
        crew_state = crew.run({"decision": decision, "student_state": state})
        selected = decision_engine.arbitrate_crew_proposals(
            decision, crew_state.get("crew_proposals", []), state
        )
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

    validated = validation_agent.validate_content(selected)
    monitor_out = monitor_agent.interact(validated, state)
    updated_state = monitor_out.get("updated_student_state", state)
    updated_state = apply_execution_feedback(
        updated_state,
        monitor_out.get("execution_feedback", {}),
        macro,
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


class QuizAnswerRequest(BaseModel):
    question: str
    selected_answer: str
    correct_answer: str
    topic: str


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
        "macro_decision": macro_with_action,
        "learning_gain_history": state.get("learning_gain_history", []),
        "accuracy_history": state.get("accuracy_history", []),
        "knowledge_state": state.get("knowledge_state", {}),
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


@app.post("/tutor/explain")
def get_explanation(body: TopicRequest):
    state = get_student_state()
    state["current_topic"] = body.topic
    _ensure_rag_ready()

    flow = _run_adaptive_learning_flow(state)
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


@app.post("/quiz/generate")
def get_quiz(body: TopicRequest):
    state = get_student_state()
    state["current_topic"] = body.topic
    subject = str(state.get("subject", "python_general"))
    level = state.get("level", "beginner")
    _ensure_rag_ready()

    macro = decision_engine.decide_macro_plan(state)
    state["macro_decision"] = macro
    micro = decision_engine.decide_next_step(state)

    practical_seed_questions = crew.practical.generate_quiz(micro, state)
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
    seed_text = "\n".join(f"- {q}" for q in practical_seed_questions[:3]) or f"- Basics of {body.topic}"

    prompt = f"""You are a {subject} quiz generator for a {level} level student.

RAG Curriculum Context (use this as the source of truth, do NOT hallucinate):
{rag_context}

Topic: {body.topic}
Decision action: {micro.get("action", "adjust_quiz")}
Candidate question intents:
{seed_text}

Generate exactly 3 MCQ questions. Return ONLY a JSON array:
[
  {{
    "question": "...",
    "options": ["A", "B", "C", "D"],
    "correct_answer": "A",
    "explanation": "...",
    "hint": "..."
  }}
]"""

    try:
        from groq import Groq

        client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )
        raw = response.choices[0].message.content.strip()
        questions = _parse_json_array(raw)
        if not questions:
            questions = _fallback_mcq_questions(body.topic, practical_seed_questions)
        return {
            "topic": body.topic,
            "questions": questions,
            "rag_grounded": bool(rag_chunks),
            "quiz_basis": quiz_basis,
            "retrieval_warning": retrieval_warning,
        }

    except Exception as e:
        print(f"GROQ QUIZ ERROR: {e}")
        return {
            "topic": body.topic,
            "questions": _fallback_mcq_questions(body.topic, practical_seed_questions),
            "rag_grounded": bool(rag_chunks),
            "quiz_basis": quiz_basis,
            "retrieval_warning": retrieval_warning,
            "error": str(e),
        }


@app.post("/quiz/submit")
def submit_answer(body: QuizAnswerRequest):
    state = get_student_state()
    state["current_topic"] = body.topic

    is_correct = body.selected_answer.strip().lower() == body.correct_answer.strip().lower()
    score = 1.0 if is_correct else 0.0

    state["last_score"] = score
    state.setdefault("learning_history", []).append(
        {
            "topic": body.topic,
            "score": score,
            "question": body.question,
        }
    )

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
        "correct": is_correct,
        "score": score,
        "updated_level": updated_state.get("level"),
        "updated_engagement": updated_state.get("engagement"),
        "updated_macro_decision": updated_state.get("macro_decision", {}),
        "knowledge_state": updated_state.get("knowledge_state", {}),
    }
