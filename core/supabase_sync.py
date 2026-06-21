"""
core/supabase_sync.py
=====================
Mirrors local student-profile state to Supabase tables.

Tables maintained:
  * user_profiles     -- scalar identity / level fields
  * learning_history  -- append-only quiz/assessment records
  * knowledge_states  -- per-concept mastery map

All writes use upsert so they are idempotent.
Errors are caught and logged -- a Supabase failure never blocks the API.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

logger = logging.getLogger(__name__)

_service_client: Client | None = None


def _get_service_client() -> Client:
    """
    Return a Supabase client that uses the service_role key.
    The service_role key bypasses Row Level Security so server-side
    writes succeed even without a user JWT context.
    Falls back to the anon key if SUPABASE_SERVICE_KEY is not set.
    """
    global _service_client
    if _service_client is None:
        url = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
        # Prefer service_role key for DB writes; fall back to anon key
        key = (
            os.getenv("SUPABASE_SERVICE_KEY", "").strip()
            or os.getenv("SUPABASE_KEY", "").strip()
        )
        if not url or not key:
            raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in .env")
        _service_client = create_client(url, key)
    return _service_client


# ---------------------------------------------------------------------------
# Individual table upserts
# ---------------------------------------------------------------------------

def upsert_user_profile(state: Dict[str, Any], user_id: str) -> None:
    """Write scalar profile fields to public.user_profiles."""
    student_id = state.get("student_id")
    if not student_id:
        return

    row = {
        "id":                       user_id,
        "student_id":               student_id,
        "full_name":                state.get("name", "Student"),
        "email":                    state.get("email", ""),
        "level":                    state.get("level", "beginner"),
        "subject":                  state.get("subject", "dsa"),
        "learning_style":           state.get("learning_style", "balanced"),
        "current_topic":            state.get("current_topic"),
        "current_subtopic":         state.get("current_subtopic"),
        "engagement":               state.get("engagement", "medium"),
        "last_score":               float(state.get("last_score", 0.0)),
        "frustration_level":        int(state.get("frustration_level", 0)),
        "engagement_score":         int(state.get("engagement_score", 5)),
        "learning_gain":            float(state.get("learning_gain", 0.0)),
        "normalized_learning_gain": float(state.get("normalized_learning_gain", 0.0)),
        "pretest_score":            state.get("pretest_score"),
        "posttest_score":           state.get("posttest_score"),
        "last_assessment_type":     state.get("last_assessment_type"),
        "last_active":              state.get("last_active") or datetime.now(timezone.utc).isoformat(),
    }

    try:
        supabase = _get_service_client()
        supabase.table("user_profiles").upsert(row, on_conflict="id").execute()
        logger.debug("upsert_user_profile OK  student_id=%s", student_id)
    except Exception as exc:
        logger.warning("upsert_user_profile FAILED  student_id=%s  error=%s", student_id, exc)


def append_learning_history(state: Dict[str, Any], user_id: str, topic: str, subtopic: str, 
                           score: float, question_count: int, passed: bool, record_type: str = "quiz") -> None:
    """Append a quiz/assessment attempt to public.learning_history."""
    student_id = state.get("student_id")
    if not student_id:
        return

    row = {
        "user_id":         user_id,
        "student_id":      student_id,
        "topic":           topic,
        "subtopic":        subtopic,
        "record_type":     record_type,
        "score":           float(score),
        "question_count":  int(question_count),
        "passed":          bool(passed),
        "recorded_at":     datetime.now(timezone.utc).isoformat(),
    }

    try:
        supabase = _get_service_client()
        supabase.table("learning_history").insert(row).execute()
        logger.debug("append_learning_history OK  student_id=%s topic=%s", student_id, topic)
    except Exception as exc:
        logger.warning("append_learning_history FAILED  student_id=%s  error=%s", student_id, exc)


def upsert_knowledge_states(state: Dict[str, Any], user_id: str) -> None:
    """Write full knowledge state snapshot to public.knowledge_state."""
    student_id = state.get("student_id")
    if not student_id:
        return

    row = {
        "user_id":              user_id,
        "student_id":           student_id,
        "state_blob":           state.get("knowledge_state", {}),
        "progress":             state.get("progress", []),
        "knowledge_events":     state.get("knowledge_events", []),
        "delivered_chunks":     state.get("delivered_chunks", {}),
        "quiz_seen_questions":  state.get("quiz_seen_questions", {}),
        "subtopic_mastery":     state.get("subtopic_mastery", {}),
        "subtopic_progress":    state.get("subtopic_progress", {}),
        "weak_areas":           state.get("weak_areas", {}),
        "strong_areas":         state.get("strong_areas", {}),
        "quiz_attempts":        state.get("quiz_attempts", {}),
        "assessment_scores":    state.get("assessment_scores", {}),
        "assessment_history":   state.get("assessment_history", []),
        "accuracy_history":     state.get("accuracy_history", []),
        "learning_gain_history": state.get("learning_gain_history", []),
        "updated_at":           datetime.now(timezone.utc).isoformat(),
    }

    try:
        supabase = _get_service_client()
        supabase.table("knowledge_state").upsert(row, on_conflict="user_id").execute()
        logger.debug("upsert_knowledge_states OK  student_id=%s", student_id)
    except Exception as exc:
        logger.warning("upsert_knowledge_states FAILED  student_id=%s  error=%s", student_id, exc)


# ---------------------------------------------------------------------------
# Combined sync
# ---------------------------------------------------------------------------

def sync_student_state(state: Dict[str, Any], user_id: Optional[str] = None) -> None:
    """
    Mirror the full student state to Supabase tables.

    Parameters
    ----------
    state   : The student state dict (same dict passed to pm.save).
    user_id : Supabase auth UUID -- required for all table writes.
    """
    if not user_id:
        logger.warning("sync_student_state called without user_id, skipping sync")
        return
        
    upsert_user_profile(state, user_id)
    upsert_knowledge_states(state, user_id)


def log_quiz_attempt(state: Dict[str, Any], user_id: str, topic: str, subtopic: str,
                    score: float, question_count: int, passed: bool, record_type: str = "quiz") -> None:
    """
    Log a single quiz/assessment attempt to learning_history.
    Call this after every quiz submit.
    """
    append_learning_history(state, user_id, topic, subtopic, score, question_count, passed, record_type)
