"""
core/question_bank_service.py
=============================
Runtime interface between the quiz-serving endpoints and the Supabase
question_bank / asked_questions tables.

Responsibilities
----------------
1. Count available unseen questions for a (topic, difficulty, pool, student).
2. Fetch exactly min(DEFAULT_QUIZ_LENGTH, available) questions, randomly ordered.
3. If available == 0 for the requested difficulty, widen to adjacent difficulties
   before declaring the pool empty (graceful degradation).
4. Log every thin-pool condition so we can prioritise custom question authoring.
5. Record served question IDs to asked_questions so they are never repeated.
6. Fail gracefully (return None) when the table does not yet exist, letting the
   caller fall back to LLM generation.

Usage
-----
    from core.question_bank_service import QuestionBankService

    qbs = QuestionBankService()                   # uses singleton Supabase client
    result = qbs.get_quiz(
        topic="Linked List",
        difficulty="medium",
        pool="practice_pool",
        student_id="stu_abc123",
        context="practice",                       # written to asked_questions.context
    )
    if result is None:
        # Table not yet populated — fall back to LLM
        ...
    else:
        questions = result["questions"]           # list[dict]
        actual_count = result["actual_count"]
        widened = result["widened_difficulty"]    # True if fallback difficulty used

Pool / context mapping
----------------------
    quiz endpoint (practice)  → pool = "practice_pool",  context = "practice"
    pretest  endpoint          → pool = "pretest_pool",   context = "pretest"
    posttest endpoint          → pool = "posttest_pool",  context = "posttest"
"""

from __future__ import annotations

import random
from typing import Any

from core.logging_utils import get_logger, log_jsonl
from core.supabase_client import get_supabase


def _get_service_client():
    """
    Return a Supabase client using the service-role key so server-side
    question_bank reads bypass RLS (which only restricts direct client access).
    Falls back to the anon-key singleton if SUPABASE_SERVICE_KEY is not set.
    """
    import os
    from supabase import create_client
    url = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
    svc_key = os.getenv("SUPABASE_SERVICE_KEY", "").strip()
    if url and svc_key:
        return create_client(url, svc_key)
    return get_supabase()  # graceful fallback to anon key

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Maximum questions per quiz session.  Tune here — referenced everywhere.
DEFAULT_QUIZ_LENGTH: int = 10

# When a difficulty pool is empty, expand to include these adjacent levels.
# "hard" falls back to medium+hard; "easy" stays easy (nothing softer exists).
DIFFICULTY_FALLBACK: dict[str, list[str]] = {
    "easy":   ["easy"],
    "medium": ["medium", "easy"],
    "hard":   ["hard", "medium"],
}

_logger = get_logger("question_bank_service", "question_bank_service.log")

# Supabase table names
_QB_TABLE = "question_bank"
_AQ_TABLE = "asked_questions"


# ---------------------------------------------------------------------------
# Public service class
# ---------------------------------------------------------------------------

class QuestionBankService:
    """
    Stateless helper that wraps all question_bank / asked_questions queries.

    Thread-safe: every method opens its own Supabase query; the underlying
    client object is a process-level singleton and is itself thread-safe.
    """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_quiz(
        self,
        *,
        topic: str,
        difficulty: str,
        pool: str,
        student_id: str,
        context: str,
    ) -> dict[str, Any] | None:
        """
        Fetch an adaptive quiz from the question bank.

        Returns a dict:
            {
                "questions": list[dict],          # question rows (prompt, solution, …)
                "actual_count": int,              # how many questions returned
                "requested_count": int,           # min(DEFAULT, available)
                "available_count": int,           # raw unseen count before capping
                "widened_difficulty": bool,       # True when fallback difficulty used
                "difficulties_used": list[str],   # difficulty/ies actually queried
                "pool": str,                      # pool that was queried
            }

        Returns None if:
          - The question_bank table does not yet exist in Supabase, OR
          - Any unexpected Supabase error occurs.
        The caller should then fall back to LLM generation.
        """
        try:
            sb = _get_service_client()
        except RuntimeError as exc:
            _logger.warning("Supabase not configured, skipping question bank: %s", exc)
            return None

        difficulties_to_try = [difficulty]       # primary attempt: exact match
        widened = False

        for attempt_difficulties in [
            [difficulty],
            DIFFICULTY_FALLBACK.get(difficulty, [difficulty]),
        ]:
            if attempt_difficulties == [difficulty] and widened:
                # Already tried exact; now trying widened — avoid duplicate run
                continue

            # Count available unseen questions for this difficulty set
            available = self._count_available(
                sb, topic, attempt_difficulties, pool, student_id
            )

            if available is None:
                # Table missing or error — signal caller to fall back
                return None

            if available > 0 or attempt_difficulties == difficulties_to_try:
                # Use this difficulty set
                difficulties_to_try = attempt_difficulties
                widened = (attempt_difficulties != [difficulty])

                requested_count = min(DEFAULT_QUIZ_LENGTH, available)

                # Log thin-pool conditions
                if requested_count < DEFAULT_QUIZ_LENGTH:
                    _logger.warning(
                        "THIN_POOL topic=%r difficulty=%r pool=%r "
                        "student=%r available=%d requested=%d widened=%s",
                        topic, attempt_difficulties, pool,
                        student_id, available, requested_count, widened,
                    )
                    log_jsonl(
                        "thin_pool.jsonl",
                        {
                            "topic": topic,
                            "difficulty": difficulty,
                            "difficulties_used": attempt_difficulties,
                            "pool": pool,
                            "student_id": student_id,
                            "available": available,
                            "requested": requested_count,
                            "default": DEFAULT_QUIZ_LENGTH,
                            "widened": widened,
                        },
                    )

                if requested_count == 0:
                    # Even the widened pool is empty
                    _logger.warning(
                        "EMPTY_POOL topic=%r difficulties=%r pool=%r student=%r — "
                        "returning empty quiz",
                        topic, attempt_difficulties, pool, student_id,
                    )
                    return {
                        "questions": [],
                        "actual_count": 0,
                        "requested_count": 0,
                        "available_count": 0,
                        "widened_difficulty": widened,
                        "difficulties_used": attempt_difficulties,
                        "pool": pool,
                    }

                # Fetch the questions
                rows = self._fetch_questions(
                    sb, topic, attempt_difficulties, pool,
                    student_id, requested_count
                )
                if rows is None:
                    return None

                # Record to asked_questions (best-effort; never block the quiz)
                self._record_asked(sb, student_id, [r["id"] for r in rows], context)

                return {
                    "questions": rows,
                    "actual_count": len(rows),
                    "requested_count": requested_count,
                    "available_count": available,
                    "widened_difficulty": widened,
                    "difficulties_used": attempt_difficulties,
                    "pool": pool,
                }

            # available == 0 for exact difficulty — widen and retry
            widened = True

        # Should not reach here; fallback just in case
        return {
            "questions": [],
            "actual_count": 0,
            "requested_count": 0,
            "available_count": 0,
            "widened_difficulty": True,
            "difficulties_used": difficulties_to_try,
            "pool": pool,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _count_available(
        self,
        sb,
        topic: str,
        difficulties: list[str],
        pool: str,
        student_id: str,
    ) -> int | None:
        """
        Return the number of unseen questions matching (topic, difficulties, pool)
        for student_id.  Returns None on error (table missing, network, etc.).

        Uses the Supabase PostgREST client rather than raw SQL so no service-key
        RPC is required — COUNT is emulated via select(..., count="exact").
        """
        try:
            # Sub-select: question IDs already seen by this student
            seen_resp = (
                sb.table(_AQ_TABLE)
                .select("question_id")
                .eq("student_id", student_id)
                .execute()
            )
            seen_ids: list[str] = [
                row["question_id"] for row in (seen_resp.data or [])
            ]

            query = (
                sb.table(_QB_TABLE)
                .select("id", count="exact")
                .eq("topic", topic)
                .in_("difficulty", difficulties)
                .eq("test_form", pool)
            )
            if seen_ids:
                query = query.not_.in_("id", seen_ids)

            resp = query.execute()
            return resp.count if resp.count is not None else len(resp.data or [])

        except Exception as exc:
            # Distinguish "table does not exist" (42P01) from other errors
            err_str = str(exc)
            if "42P01" in err_str or "does not exist" in err_str.lower():
                _logger.info(
                    "question_bank table not yet created — "
                    "caller should fall back to LLM generation."
                )
            else:
                _logger.error(
                    "Error counting available questions "
                    "(topic=%r diff=%r pool=%r student=%r): %s",
                    topic, difficulties, pool, student_id, exc,
                )
            return None

    def _fetch_questions(
        self,
        sb,
        topic: str,
        difficulties: list[str],
        pool: str,
        student_id: str,
        count: int,
    ) -> list[dict] | None:
        """
        Fetch `count` unseen question rows, in random order.
        Returns None on Supabase error.
        """
        try:
            seen_resp = (
                sb.table(_AQ_TABLE)
                .select("question_id")
                .eq("student_id", student_id)
                .execute()
            )
            seen_ids: list[str] = [
                row["question_id"] for row in (seen_resp.data or [])
            ]

            query = (
                sb.table(_QB_TABLE)
                .select("id, topic, subtopic, difficulty, prompt, solution, test_cases, test_form, source")
                .eq("topic", topic)
                .in_("difficulty", difficulties)
                .eq("test_form", pool)
            )
            if seen_ids:
                query = query.not_.in_("id", seen_ids)

            # Fetch a small oversample then shuffle locally — Supabase PostgREST
            # doesn't expose ORDER BY random() via the client library.
            oversample = min(count * 3, count + 30)
            resp = query.limit(oversample).execute()
            rows: list[dict] = resp.data or []
            random.shuffle(rows)
            return rows[:count]

        except Exception as exc:
            _logger.error(
                "Error fetching questions "
                "(topic=%r diff=%r pool=%r student=%r count=%d): %s",
                topic, difficulties, pool, student_id, count, exc,
            )
            return None

    def _record_asked(
        self,
        sb,
        student_id: str,
        question_ids: list[str],
        context: str,
    ) -> None:
        """
        Append rows to asked_questions for each served question.
        Never raises — failures are logged and swallowed so the quiz
        response is never blocked by a write error.
        """
        if not question_ids:
            return
        try:
            rows = [
                {"student_id": student_id, "question_id": qid, "context": context}
                for qid in question_ids
            ]
            sb.table(_AQ_TABLE).insert(rows).execute()
        except Exception as exc:
            _logger.error(
                "Failed to record asked_questions for student=%r: %s",
                student_id, exc,
            )


# ---------------------------------------------------------------------------
# Module-level singleton — import this rather than instantiating per request
# ---------------------------------------------------------------------------
_service: QuestionBankService | None = None


def get_question_bank_service() -> QuestionBankService:
    """Return the process-level QuestionBankService singleton."""
    global _service
    if _service is None:
        _service = QuestionBankService()
    return _service
