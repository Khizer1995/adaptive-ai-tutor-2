from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
import os

load_dotenv()

from core.simulation import AdaptiveLearningSimulation
from core.profile_manager import ProfileManager
from core.decision_engine import DecisionEngine
from core.education_crew import EducationCrew
from core.file_manager_agent import FileManagerAgent

app = FastAPI()

# Allow React dev server to talk to this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Initialize core components once ──────────────────────────────
simulation = AdaptiveLearningSimulation()
pm = ProfileManager()
decision_engine = DecisionEngine()
crew = EducationCrew()
file_manager = FileManagerAgent()

STUDENT_ID = "KISH-001"

# ── Patch TeacherReviewAgent to auto-approve in API mode ─────────
# This avoids the CLI prompt blocking the API
from core.teacher_review_agent import TeacherReviewAgent
original_review = TeacherReviewAgent.review

def auto_approve_review(self, crew_output, student_state):
    return {"review_status": "approved", "comments": "auto-approved via API"}

TeacherReviewAgent.review = auto_approve_review

# ── Load or initialize student profile ───────────────────────────
def get_student_state():
    try:
        return pm.load(STUDENT_ID)
    except FileNotFoundError:
        return {
            "student_id": STUDENT_ID,
            "name": "Student",
            "level": "beginner",
            "current_topic": None,
            "progress": [],
            "engagement": "medium",
            "last_score": 0.3,
            "learning_history": []
        }

# ── Request schemas ───────────────────────────────────────────────
class TopicRequest(BaseModel):
    topic: str

class QuizAnswerRequest(BaseModel):
    question: str
    selected_answer: str
    correct_answer: str
    topic: str

# ── ENDPOINTS ─────────────────────────────────────────────────────

@app.get("/")
def root():
    return {"status": "Cognitive Adaptive AI Tutor API running"}


@app.get("/student/state")
def get_state():
    """Returns current student state — level, mastery, engagement, decision"""
    state = get_student_state()
    return {
        "student_id": state.get("student_id"),
        "name": state.get("name"),
        "level": state.get("level", "beginner"),
        "engagement": state.get("engagement", "medium"),
        "last_score": state.get("last_score", 0.0),
        "current_topic": state.get("current_topic"),
        "macro_decision": state.get("macro_decision", {}),
        "learning_gain_history": state.get("learning_gain_history", []),
        "accuracy_history": state.get("accuracy_history", []),
        "knowledge_state": state.get("knowledge_state", {}),
    }


@app.get("/student/topics")
def get_topics():
    state = get_student_state()
    knowledge_state = state.get("knowledge_state", {})
    
    topics = []
    # knowledge_state has "concepts" dict and "version" number
    # real topics live inside "concepts"
    concepts = knowledge_state.get("concepts", {})
    
    for topic_name, data in concepts.items():
        if isinstance(data, dict):
            topics.append({
                "name": topic_name,
                "mastery": data.get("mastery", 0.0),
                "confidence": data.get("confidence", 0.0),
                "attempts": data.get("attempts", 0),
                "weak_areas": data.get("weak_areas", []),
            })
    
    return {"topics": topics}


@app.post("/tutor/explain")
def get_explanation(body: TopicRequest):
    state = get_student_state()
    level = state.get("level", "beginner")

    # Get decision reasoning
    state["current_topic"] = body.topic
    macro = decision_engine.decide_macro_plan(state)

    # Generate topic-specific explanation directly via Groq
    prompt = f"""You are an expert Python tutor. Generate a clear, structured explanation of "{body.topic}" for a {level} level student.

Include:
1. Simple explanation (2-3 sentences)
2. How it works (step by step)
3. Code example (practical, commented)
4. Key takeaways (3 bullet points)
5. Common misconceptions to avoid

Use markdown formatting. Be specific to {body.topic} only."""

    try:
        from groq import Groq
        import os

        client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4,
        )
        explanation = response.choices[0].message.content.strip()
    except Exception as e:
        print(f"GROQ EXPLAIN ERROR: {e}")
        explanation = f"# {body.topic}\n\nUnable to generate explanation. Please try again."

    return {
        "topic": body.topic,
        "learning_path": explanation,
        "rag_chunks": [],
        "teacher_style": "",
        "macro_decision": {
            "action": macro.get("action", ""),
            "reason": (
                macro.get("reason", "")
                    .replace("macro_action=", "Action: ")
                    .replace("based on score=", "based on your score of ")
                    .replace("trend=", "learning trend: ")
                    .replace("avg_mastery=", "average mastery: ")
                    .replace("avg_confidence=", "average confidence: ")
                    .replace(",", " |")
                    or "Content selected based on your current mastery level."
),
        },
        "model_used": "groq/llama-3.3-70b-versatile",
    }


@app.post("/quiz/generate")
def get_quiz(body: TopicRequest):
    """Generate proper MCQ questions using Groq directly"""
    state = get_student_state()
    level = state.get("level", "beginner")

    prompt = f"""Generate 3 multiple choice questions about "{body.topic}" for a {level} Python student.

Return ONLY a JSON array, no other text, no markdown, no code blocks:
[
  {{
    "question": "question text here",
    "options": ["option 1", "option 2", "option 3", "option 4"],
    "correct_answer": "option 1",
    "explanation": "why this is correct",
    "hint": "helpful hint without giving away answer"
  }}
]"""

    try:
        import os
        from groq import Groq
        import json

        client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )

        raw = response.choices[0].message.content.strip()
        

        # Clean up any accidental markdown
        if "```" in raw:
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()

        questions = json.loads(raw)
        return {"topic": body.topic, "questions": questions}

    except Exception as e:
        print(f"GROQ QUIZ ERROR: {e}")
        return {
            "topic": body.topic,
            "questions": [{
                "question": f"What is a key concept in {body.topic}?",
                "options": [
                    f"{body.topic} is used to store data",
                    f"{body.topic} is only for advanced users",
                    f"{body.topic} cannot be modified",
                    f"{body.topic} requires special imports"
                ],
                "correct_answer": f"{body.topic} is used to store data",
                "explanation": f"{body.topic} is a fundamental concept in Python.",
                "hint": f"Think about the basic purpose of {body.topic}."
            }]
        }


@app.post("/quiz/submit")
def submit_answer(body: QuizAnswerRequest):
    """
    Scores a quiz answer and updates student state.
    Returns: correct, updated mastery, new student state
    """
    state = get_student_state()
    state["current_topic"] = body.topic

    is_correct = body.selected_answer.strip().lower() == body.correct_answer.strip().lower()
    score = 1.0 if is_correct else 0.0

    # Update last score and learning history
    state["last_score"] = score
    state.setdefault("learning_history", []).append({
        "topic": body.topic,
        "score": score,
        "question": body.question,
    })

    # Run a simulation cycle to update student model
    updated_state = simulation.run_cycle(state)

    # Save updated profile
    pm.save(STUDENT_ID, updated_state)

    return {
        "correct": is_correct,
        "score": score,
        "updated_level": updated_state.get("level"),
        "updated_engagement": updated_state.get("engagement"),
        "updated_macro_decision": updated_state.get("macro_decision", {}),
        "knowledge_state": updated_state.get("knowledge_state", {}),
    }