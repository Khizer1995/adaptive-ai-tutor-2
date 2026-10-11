"""
core/question_bank_service.py
=============================
Runtime interface between the quiz-serving endpoints and the Supabase
question_bank / asked_questions tables.

Responsibilities
----------------
1. Count available unseen questions for a (topic, difficulty, pool, student,
   question_type).
2. Fetch exactly min(DEFAULT_QUIZ_LENGTH, available) questions, randomly ordered.
3. If available == 0 for the requested difficulty, widen to adjacent difficulties
   before declaring the pool empty (graceful degradation).
4. Log every thin-pool condition so we can prioritise custom question authoring.
5. Record served question IDs to asked_questions AT FETCH TIME with correct=NULL
   so non-repetition is enforced at show-time, not submit-time.  A student who
   abandons a quiz without submitting will never see those questions again.
6. grade() UPDATE that row with the student's correct bool and returns
   {correct: bool, explanation: str}.  This keeps grading atomic with recording.
7. For MCQ rows: sanitise the fetch payload — correct_index and explanation are
   NEVER returned to the frontend from get_quiz(); they are only disclosed by
   grade() after the student submits an answer.
8. Assert unique IDs and unique normalised prompts within every quiz batch.
9. Fail gracefully (return None) when the table does not yet exist, letting the
   caller fall back to whatever it chooses (for pretest/posttest: return empty).

Pool / context / question_type mapping
---------------------------------------
  quiz/generate (practice) -> pool="practice_pool", context="practice",  question_type=None (any)
  /quiz/pretest            -> pool="pretest_pool",  context="pretest",   question_type="mcq"
  /quiz/posttest           -> pool="posttest_pool", context="posttest",  question_type="mcq"

Shape returned per question (SANITISED — NO correct_index or explanation)
--------------------------------------------------------------------------
MCQ row:
  {
    "id":            str,
    "question":      str,   # the prompt text (renamed for UI compatibility)
    "options":       list,  # 4 strings, shuffled per request
    "topic":         str,
    "subtopic":      str,
    "difficulty":    str,
    "question_type": "mcq",
  }

Code row (unchanged shape -- returned as-is for practice quiz):
  {
    "id":            str,
    "question":      str,   # prompt
    "topic":         str,
    ...all other columns...
    "question_type": "code",
  }

grade() return value
--------------------
  {
    "correct":     bool,
    "explanation": str,
  }
"""

from __future__ import annotations

import random
import unicodedata
from typing import Any

from core.logging_utils import get_logger, log_jsonl
from core.supabase_client import get_supabase


def _get_service_client():
    """
    Return a Supabase client using the service-role key so server-side
    question_bank reads bypass RLS.
    Falls back to the anon-key singleton if SUPABASE_SERVICE_KEY is not set.
    """
    import os
    from supabase import create_client
    url = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
    svc_key = os.getenv("SUPABASE_SERVICE_KEY", "").strip()
    if url and svc_key:
        return create_client(url, svc_key)
    return get_supabase()


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Maximum questions per quiz session.
DEFAULT_QUIZ_LENGTH: int = 10

# When a difficulty pool is empty, expand to include adjacent levels.
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
# Internal MCQ helpers
# ---------------------------------------------------------------------------

def _normalize_text(s: str) -> str:
    """Lowercase, strip accents, collapse whitespace — used for uniqueness checks."""
    s = str(s or "").strip().lower()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return " ".join(s.split())


def _sanitise_mcq(row: dict) -> dict:
    """
    Convert a raw question_bank MCQ row into the SANITISED shape the frontend
    receives at fetch time.

    Security contract:
      • correct_index is NOT included in the returned dict.
      • explanation is NOT included in the returned dict.
      • Options are returned in their ORIGINAL DB order so that chosen_index
        submitted by the client maps directly to the DB's correct_index.
        (Shuffling here would make chosen_index ambiguous on the server.)

    Grading happens exclusively server-side via grade().
    """
    options: list[str] = list(row.get("options") or [])

    return {
        "id":            row.get("id", ""),
        "question":      row.get("prompt", ""),   # renamed for UI compatibility
        "options":       options,                 # original order — no shuffle
        "topic":         row.get("topic", ""),
        "subtopic":      row.get("subtopic", ""),
        "difficulty":    row.get("difficulty", ""),
        "question_type": "mcq",
        # correct_index and explanation intentionally omitted
    }


def _resolve_code(row: dict) -> dict:
    """Rename 'prompt' -> 'question' and add question_type for code rows."""
    out = dict(row)
    out.setdefault("question_type", "code")
    if "prompt" in out and "question" not in out:
        out["question"] = out.pop("prompt")
    elif "prompt" in out:
        out.setdefault("question", out["prompt"])
    return out


def _assert_unique_batch(rows: list[dict], label: str) -> None:
    """
    Assert that all returned questions have unique IDs and unique normalised
    prompts.  Logs a warning (does not raise) so a DB data error never
    crashes a student's quiz.
    """
    seen_ids: set[str] = set()
    seen_prompts: set[str] = set()
    for row in rows:
        qid = str(row.get("id", ""))
        prompt = _normalize_text(row.get("prompt") or row.get("question") or "")
        if qid in seen_ids:
            _logger.warning("Duplicate question ID in batch [%s]: %r", label, qid)
        if prompt and prompt in seen_prompts:
            _logger.warning("Duplicate normalised prompt in batch [%s]: %r", label, prompt[:80])
        seen_ids.add(qid)
        if prompt:
            seen_prompts.add(prompt)


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
        question_type: str | None = None,
        subtopic: str | None = None,
    ) -> dict[str, Any] | None:
        """
        Fetch an adaptive quiz from the question bank.

        Records served question IDs to asked_questions AT FETCH TIME with
        correct=NULL.  Non-repetition is enforced at show-time: a student who
        closes the tab before submitting will never see those questions again.

        Parameters
        ----------
        topic          : curriculum topic (e.g. "array" - will be normalized to "Array")
        difficulty     : "easy" | "medium" | "hard"
        pool           : "pretest_pool" | "posttest_pool" | "practice_pool"
        student_id     : used to exclude already-seen questions
        context        : written to asked_questions.context
        question_type  : "mcq" | "code" | None (None = any type)
        subtopic       : preferred subtopic; if provided, the service fills
                         from this subtopic first, then tops up from others
                         in the same topic.

        Returns a dict:
            {
                "questions":          list[dict],   # sanitised MCQ / code objects
                "actual_count":       int,
                "requested_count":    int,
                "available_count":    int,
                "widened_difficulty": bool,
                "difficulties_used":  list[str],
                "pool":               str,
            }
        or None on Supabase error / missing table (caller should handle gracefully).
        """
        # Normalize topic to title-case to match question_bank.topic column
        # (curriculum uses lowercase 'array'/'queue'/'graph', DB uses 'Array'/'Queue'/'Graph')
        topic = topic.strip().title()
        
        # Normalize subtopic from underscore format to title-case with spaces
        # (curriculum uses 'array_operations', DB uses 'Array Operations')
        if subtopic:
            # Convert 'array_operations' -> 'Array Operations'
            subtopic = subtopic.replace("_", " ").strip().title()
            _logger.info(f"Normalized subtopic to: {subtopic!r}")
        
        try:
            sb = _get_service_client()
        except RuntimeError as exc:
            _logger.warning("Supabase not configured, skipping question bank: %s", exc)
            return None

        difficulties_to_try = [difficulty]
        widened = False

        for attempt_difficulties in [
            [difficulty],
            DIFFICULTY_FALLBACK.get(difficulty, [difficulty]),
        ]:
            if attempt_difficulties == [difficulty] and widened:
                continue

            # ------------------------------------------------------------------
            # Step 1: count available unseen questions (preferred subtopic first)
            # ------------------------------------------------------------------
            if subtopic:
                available_preferred = self._count_available(
                    sb, topic, attempt_difficulties, pool, student_id,
                    question_type=question_type, subtopic=subtopic,
                )
                available_other = self._count_available(
                    sb, topic, attempt_difficulties, pool, student_id,
                    question_type=question_type, subtopic=None, exclude_subtopic=subtopic,
                )
                available_total = (
                    None if (available_preferred is None or available_other is None)
                    else available_preferred + available_other
                )
            else:
                available_preferred = None
                available_other     = None
                available_total = self._count_available(
                    sb, topic, attempt_difficulties, pool, student_id,
                    question_type=question_type,
                )

            if available_total is None:
                return None   # table missing or error

            if available_total > 0 or attempt_difficulties == difficulties_to_try:
                difficulties_to_try = attempt_difficulties
                widened = (attempt_difficulties != [difficulty])

                requested_count = min(DEFAULT_QUIZ_LENGTH, available_total)

                # Log thin pool
                if requested_count < DEFAULT_QUIZ_LENGTH:
                    _logger.warning(
                        "THIN_POOL topic=%r difficulty=%r pool=%r type=%r "
                        "student=%r available=%d requested=%d widened=%s",
                        topic, attempt_difficulties, pool, question_type,
                        student_id, available_total, requested_count, widened,
                    )
                    log_jsonl("thin_pool.jsonl", {
                        "topic": topic, "difficulty": difficulty,
                        "difficulties_used": attempt_difficulties, "pool": pool,
                        "question_type": question_type, "student_id": student_id,
                        "available": available_total, "requested": requested_count,
                        "default": DEFAULT_QUIZ_LENGTH, "widened": widened,
                    })

                if requested_count == 0:
                    # Special handling for practice_pool: fetch previously attempted questions
                    if pool == "practice_pool":
                        _logger.info(
                            "PRACTICE_POOL_EXHAUSTED topic=%r difficulty=%r student=%r - "
                            "fetching adaptive repeat questions",
                            topic, attempt_difficulties, student_id,
                        )
                        repeat_quiz = self._fetch_adaptive_repeat_questions(
                            sb, topic, attempt_difficulties, student_id, 
                            question_type, subtopic
                        )
                        if repeat_quiz and repeat_quiz.get("questions"):
                            return repeat_quiz
                    
                    _logger.warning(
                        "EMPTY_POOL topic=%r difficulties=%r pool=%r type=%r student=%r",
                        topic, attempt_difficulties, pool, question_type, student_id,
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

                # ------------------------------------------------------------------
                # Step 2: fetch questions (preferred subtopic first, then fill up)
                # ------------------------------------------------------------------
                rows: list[dict] = []
                if subtopic and available_preferred and available_preferred > 0:
                    want_pref = min(requested_count, available_preferred)
                    pref_rows = self._fetch_questions(
                        sb, topic, attempt_difficulties, pool, student_id,
                        want_pref, question_type=question_type, subtopic=subtopic,
                    )
                    if pref_rows is None:
                        return None
                    rows.extend(pref_rows)

                if len(rows) < requested_count:
                    remaining = requested_count - len(rows)
                    fill_rows = self._fetch_questions(
                        sb, topic, attempt_difficulties, pool, student_id,
                        remaining, question_type=question_type,
                        subtopic=None,
                        exclude_subtopic=subtopic if subtopic else None,
                        exclude_ids=[r["id"] for r in rows],
                    )
                    if fill_rows is None:
                        return None
                    rows.extend(fill_rows)

                if not rows:
                    return {
                        "questions": [], "actual_count": 0, "requested_count": requested_count,
                        "available_count": available_total, "widened_difficulty": widened,
                        "difficulties_used": attempt_difficulties, "pool": pool,
                    }

                # Assert uniqueness in the raw rows before resolving
                _assert_unique_batch(rows, label=f"{topic}/{pool}")

                # ── Record to asked_questions AT FETCH TIME with correct=NULL ──
                # Non-repetition is enforced at show-time.  Students who abandon
                # a quiz without submitting will never see those questions again.
                self._record_asked(sb, student_id, [r["id"] for r in rows], context)

                # Resolve to sanitised UI shape (no correct_index / explanation)
                resolved = self._resolve_rows(rows)

                return {
                    "questions":          resolved,
                    "actual_count":       len(resolved),
                    "requested_count":    requested_count,
                    "available_count":    available_total,
                    "widened_difficulty": widened,
                    "difficulties_used":  attempt_difficulties,
                    "pool":               pool,
                }

            widened = True

        # Should not reach here
        return {
            "questions": [], "actual_count": 0, "requested_count": 0,
            "available_count": 0, "widened_difficulty": True,
            "difficulties_used": difficulties_to_try, "pool": pool,
        }

    def grade(
        self,
        *,
        question_id: str,
        chosen_index: int,
        student_id: str,
        context: str,
    ) -> dict[str, Any]:
        """
        Server-side grading — the ONLY path that reads correct_index and
        returns explanation.

        Steps:
          1. Fetch correct_index and explanation from question_bank for question_id.
          2. Compare chosen_index == correct_index.
          3. UPDATE asked_questions SET correct=<result>
             WHERE student_id=student_id AND question_id=question_id
             (targets the NULL row written at fetch time).
          4. Return {correct: bool, explanation: str}.

        The correct_index and explanation are read directly from the DB and
        never stored in the response object alongside question content.
        """
        try:
            sb = _get_service_client()
        except RuntimeError as exc:
            _logger.error("Supabase not configured in grade(): %s", exc)
            return {"correct": False, "explanation": "Grading service unavailable."}

        try:
            # 1. Fetch grading data from DB
            resp = (
                sb.table(_QB_TABLE)
                .select("correct_index, explanation, question_type")
                .eq("id", question_id)
                .limit(1)
                .execute()
            )
            rows = resp.data or []
            if not rows:
                _logger.error("grade(): question_id=%r not found in question_bank", question_id)
                return {"correct": False, "explanation": "Question not found."}

            row = rows[0]
            qtype = str(row.get("question_type") or "mcq")

            if qtype != "mcq":
                _logger.warning(
                    "grade() called for non-MCQ question_id=%r (type=%r) — returning False",
                    question_id, qtype,
                )
                return {"correct": False, "explanation": "Not an MCQ question."}

            correct_index: int = int(row.get("correct_index", -1))
            explanation: str = str(row.get("explanation") or "")
            is_correct: bool = (chosen_index == correct_index)

            # 2. UPDATE the asked_questions row written at fetch time
            #    Match on student_id + question_id + correct IS NULL to avoid
            #    double-updating if grade() is called more than once.
            try:
                (
                    sb.table(_AQ_TABLE)
                    .update({"correct": is_correct})
                    .eq("student_id", student_id)
                    .eq("question_id", question_id)
                    .is_("correct", "null")  # only update the ungraded row
                    .execute()
                )
            except Exception as update_exc:
                # Non-fatal: the question was already marked at show-time;
                # grading the answer is best-effort on the DB side.
                _logger.warning(
                    "grade() UPDATE asked_questions failed for "
                    "student=%r question=%r: %s",
                    student_id, question_id, update_exc,
                )

            return {
                "correct":     is_correct,
                "explanation": explanation,
            }

        except Exception as exc:
            _logger.error(
                "grade() failed for question_id=%r student=%r: %s",
                question_id, student_id, exc,
            )
            return {"correct": False, "explanation": "Grading service error."}

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
        *,
        question_type: str | None = None,
        subtopic: str | None = None,
        exclude_subtopic: str | None = None,
    ) -> int | None:
        """
        Return the number of unseen questions matching the filters.
        Returns None on error (table missing, network, etc.).
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
                .select("id", count="exact")
                .eq("topic", topic)
                .in_("difficulty", difficulties)
                .eq("test_form", pool)
            )
            if question_type:
                query = query.eq("question_type", question_type)
            if subtopic:
                query = query.eq("subtopic", subtopic)
            if exclude_subtopic:
                query = query.neq("subtopic", exclude_subtopic)
            if seen_ids:
                query = query.not_.in_("id", seen_ids)

            resp = query.execute()
            return resp.count if resp.count is not None else len(resp.data or [])

        except Exception as exc:
            err_str = str(exc)
            if "42P01" in err_str or "does not exist" in err_str.lower():
                _logger.info("question_bank table not yet created -- caller will handle.")
            else:
                _logger.error(
                    "Error counting available questions "
                    "(topic=%r diff=%r pool=%r type=%r student=%r): %s",
                    topic, difficulties, pool, question_type, student_id, exc,
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
        *,
        question_type: str | None = None,
        subtopic: str | None = None,
        exclude_subtopic: str | None = None,
        exclude_ids: list[str] | None = None,
    ) -> list[dict] | None:
        """Fetch `count` unseen question rows, in random order. Returns None on error."""
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
            if exclude_ids:
                seen_ids = list(set(seen_ids) | set(exclude_ids))

            query = (
                sb.table(_QB_TABLE)
                .select(
                    "id, topic, subtopic, difficulty, prompt, solution, test_cases, "
                    "test_form, source, question_type, options, correct_index, "
                    "explanation, distractor_tags, concept, form"
                )
                .eq("topic", topic)
                .in_("difficulty", difficulties)
                .eq("test_form", pool)
            )
            if question_type:
                query = query.eq("question_type", question_type)
            if subtopic:
                query = query.eq("subtopic", subtopic)
            if exclude_subtopic:
                query = query.neq("subtopic", exclude_subtopic)
            if seen_ids:
                query = query.not_.in_("id", seen_ids)

            oversample = min(count * 3, count + 30)
            resp = query.limit(oversample).execute()
            rows: list[dict] = resp.data or []
            random.shuffle(rows)
            return rows[:count]

        except Exception as exc:
            _logger.error(
                "Error fetching questions "
                "(topic=%r diff=%r pool=%r type=%r student=%r count=%d): %s",
                topic, difficulties, pool, question_type, student_id, count, exc,
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
        Append rows to asked_questions for each served question at FETCH TIME.
        correct is NULL — it will be UPDATE'd by grade() when the student submits.
        Never raises — failures are logged and swallowed.
        """
        if not question_ids:
            return
        try:
            rows = [
                {
                    "student_id":  student_id,
                    "question_id": qid,
                    "context":     context,
                    "correct":     None,   # graded later by grade()
                }
                for qid in question_ids
            ]
            sb.table(_AQ_TABLE).insert(rows).execute()
        except Exception as exc:
            _logger.error(
                "Failed to record asked_questions for student=%r: %s",
                student_id, exc,
            )

    def _resolve_rows(self, rows: list[dict]) -> list[dict]:
        """
        Convert raw DB rows to sanitised UI-ready question dicts based on
        question_type.  MCQ rows have correct_index and explanation stripped.
        """
        resolved = []
        for row in rows:
            qtype = str(row.get("question_type") or "code")
            if qtype == "mcq":
                resolved.append(_sanitise_mcq(row))
            else:
                resolved.append(_resolve_code(row))
        return resolved

    def _fetch_adaptive_repeat_questions(
        self,
        sb,
        topic: str,
        difficulties: list[str],
        student_id: str,
        question_type: str | None = None,
        subtopic: str | None = None,
    ) -> dict[str, Any] | None:
        """
        When practice pool is exhausted, build an adaptive quiz from:
        1. 1-2 questions answered correctly in practice (reinforcement)
        2. ~4-5 questions answered wrong in practice (remediation)
        3. ~3-4 questions answered wrong in pretest (addressing gaps)
        
        All randomized for a ~10 question adaptive quiz.
        """
        try:
            # Fetch student's question history with correctness
            history_resp = (
                sb.table("asked_questions")
                .select("question_id, correct, context")
                .eq("student_id", student_id)
                .not_.is_("correct", "null")  # only graded questions
                .execute()
            )
            history = history_resp.data or []
            
            # Categorize by context and correctness
            practice_correct_ids = [
                h["question_id"] for h in history 
                if h.get("context") == "practice" and h.get("correct") is True
            ]
            practice_wrong_ids = [
                h["question_id"] for h in history 
                if h.get("context") == "practice" and h.get("correct") is False
            ]
            pretest_wrong_ids = [
                h["question_id"] for h in history 
                if h.get("context") == "pretest" and h.get("correct") is False
            ]
            
            _logger.info(
                "ADAPTIVE_REPEAT_POOL student=%r topic=%r: "
                "practice_correct=%d practice_wrong=%d pretest_wrong=%d",
                student_id, topic, len(practice_correct_ids), 
                len(practice_wrong_ids), len(pretest_wrong_ids)
            )
            
            # Build query for each category
            def fetch_by_ids(ids: list[str], limit: int) -> list[dict]:
                if not ids:
                    return []
                query = (
                    sb.table(_QB_TABLE)
                    .select(
                        "id, topic, subtopic, difficulty, prompt, solution, test_cases, "
                        "test_form, source, question_type, options, correct_index, "
                        "explanation, distractor_tags, concept, form"
                    )
                    .eq("topic", topic)
                    .in_("difficulty", difficulties)
                    .in_("id", ids[:min(len(ids), limit * 3)])  # oversample
                )
                if question_type:
                    query = query.eq("question_type", question_type)
                if subtopic:
                    query = query.eq("subtopic", subtopic)
                
                resp = query.execute()
                rows = resp.data or []
                random.shuffle(rows)
                return rows[:limit]
            
            # Fetch from each category with desired limits
            correct_questions = fetch_by_ids(practice_correct_ids, limit=2)
            practice_wrong_questions = fetch_by_ids(practice_wrong_ids, limit=5)
            pretest_wrong_questions = fetch_by_ids(pretest_wrong_ids, limit=4)
            
            # Combine and shuffle
            all_questions = correct_questions + practice_wrong_questions + pretest_wrong_questions
            random.shuffle(all_questions)
            
            # Cap at DEFAULT_QUIZ_LENGTH
            all_questions = all_questions[:DEFAULT_QUIZ_LENGTH]
            
            if not all_questions:
                _logger.warning(
                    "ADAPTIVE_REPEAT_EMPTY student=%r topic=%r - no historical questions available",
                    student_id, topic
                )
                return None
            
            _logger.info(
                "ADAPTIVE_REPEAT_SUCCESS student=%r topic=%r: "
                "fetched %d questions (correct=%d, practice_wrong=%d, pretest_wrong=%d)",
                student_id, topic, len(all_questions),
                len(correct_questions), len(practice_wrong_questions), 
                len(pretest_wrong_questions)
            )
            
            # Record these as new attempts (so we track if they improve)
            self._record_asked(sb, student_id, [q["id"] for q in all_questions], "practice")
            
            # Resolve to sanitised format
            resolved = self._resolve_rows(all_questions)
            
            return {
                "questions": resolved,
                "actual_count": len(resolved),
                "requested_count": DEFAULT_QUIZ_LENGTH,
                "available_count": len(all_questions),
                "widened_difficulty": False,
                "difficulties_used": difficulties,
                "pool": "practice_pool_adaptive_repeat",
                "adaptive_repeat": True,
                "composition": {
                    "reinforcement": len(correct_questions),
                    "practice_remediation": len(practice_wrong_questions),
                    "pretest_gaps": len(pretest_wrong_questions),
                }
            }
            
        except Exception as exc:
            _logger.error(
                "Failed to fetch adaptive repeat questions for student=%r topic=%r: %s",
                student_id, topic, exc
            )
            return None


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
_service: QuestionBankService | None = None


def get_question_bank_service() -> QuestionBankService:
    """Return the process-level QuestionBankService singleton."""
    global _service
    if _service is None:
        _service = QuestionBankService()
    return _service
