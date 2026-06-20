"""
core/supabase_sync.py
=====================
Mirrors local student-profile state to Supabase tables.

Three tables are maintained:
  * user_profiles   -- scalar identity / level fields
  * learning_state  -- all learning metrics and history arrays
  * knowledge_state -- per-concept mastery map

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
        "student_id":     student_id,
        "user_id":        user_id,
        "name":           state.get("name", "Student"),
        "level":          state.get("level", "beginner"),
        "subject":        state.get("subject", "dsa"),
        "engagement":     state.get("engagement", "medium"),
        "learning_style": state.get("learning_style", "balanced"),
        "last_score":     float(state.get("last_score", 0.0)),
        "last_active":    state.get("last_active") or datetime.now(timezone.utc).isoformat(),
    }

    try:
        supabase = _get_service_client()
        supabase.table("user_profiles").upsert(row, on_conflict="student_id").execute()
        logger.debug("upsert_user_profile OK  student_id=%s", student_id)
    except Exception as exc:
        logger.warning("upsert_user_profile FAILED  student_id=%s  error=%s", student_id, exc)


def upsert_learning_state(state: Dict[str, Any]) -> None:
    """Write learning metrics and history arrays to public.learning_state."""
    student_id = state.get("student_id")
    if not student_id:
        return

    row = {
        "student_id":               student_id,
        "current_topic":            state.get("current_topic"),
        "current_subtopic":         state.get("current_subtopic"),
        "pretest_score":            state.get("pretest_score"),
        "posttest_score":           state.get("posttest_score"),
        "learning_gain":            float(state.get("learning_gain", 0.0)),
        "normalized_learning_gain": float(state.get("normalized_learning_gain", 0.0)),
        "progress":                 state.get("progress", []),
        "learning_history":         state.get("learning_history", []),
        "accuracy_history":         state.get("accuracy_history", []),
        "learning_gain_history":    state.get("learning_gain_history", []),
        "assessment_scores":        state.get("assessment_scores", {}),
        "assessment_history":       state.get("assessment_history", []),
        "subtopic_mastery":         state.get("subtopic_mastery", {}),
        "subtopic_progress":        state.get("subtopic_progress", {}),
        "weak_areas":               state.get("weak_areas", {}),
        "strong_areas":             state.get("strong_areas", {}),
        "quiz_attempts":            state.get("quiz_attempts", {}),
        "updated_at":               datetime.now(timezone.utc).isoformat(),
    }

    try:
        supabase = _get_service_client()
        supabase.table("learning_state").upsert(row, on_conflict="student_id").execute()
        logger.debug("upsert_learning_state OK  student_id=%s", student_id)
    except Exception as exc:
        logger.warning("upsert_learning_state FAILED  student_id=%s  error=%s", student_id, exc)


def upsert_knowledge_state(state: Dict[str, Any]) -> None:
    """Write per-concept mastery map to public.knowledge_state."""
    student_id = state.get("student_id")
    if not student_id:
        return

    raw_ks = state.get("knowledge_state", {})
    if not isinstance(raw_ks, dict):
        raw_ks = {}

    row = {
        "student_id": student_id,
        "concepts":   raw_ks.get("concepts", {}),
        "version":    int(raw_ks.get("version", 1)),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    try:
        supabase = _get_service_client()
        supabase.table("knowledge_state").upsert(row, on_conflict="student_id").execute()
        logger.debug("upsert_knowledge_state OK  student_id=%s", student_id)
    except Exception as exc:
        logger.warning("upsert_knowledge_state FAILED  student_id=%s  error=%s", student_id, exc)


# ---------------------------------------------------------------------------
# Combined sync
# ---------------------------------------------------------------------------

def sync_student_state(state: Dict[str, Any], user_id: Optional[str] = None) -> None:
    """
    Mirror the full student state to all three Supabase tables.

    Parameters
    ----------
    state   : The student state dict (same dict passed to pm.save).
    user_id : Supabase auth UUID -- required to write user_profiles.
              If omitted, user_profiles is skipped (learning_state and
              knowledge_state are still updated via the FK that already exists).
    """
    if user_id:
        upsert_user_profile(state, user_id)
    upsert_learning_state(state)
    upsert_knowledge_state(state)
