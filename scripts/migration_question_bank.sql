-- ============================================================================
-- Cognitive Adaptive AI Tutor — Question Bank Migration
-- ============================================================================
-- Adds two new tables:
--   public.question_bank    — static pool of tagged quiz questions
--   public.asked_questions  — per-student usage tracking (no-repeat guarantee)
--
-- Run in the Supabase SQL Editor:
--   Dashboard → SQL Editor → New Query → Paste → Run
--
-- Safe to re-run: all statements use IF NOT EXISTS / OR REPLACE.
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 1. question_bank
--    One row per question. Populated offline by ingest_question_bank.py.
--    test_form partitions questions into disjoint pre-test / post-test /
--    practice pools so a student never sees the same question in both their
--    pre-test and post-test for a given topic.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.question_bank (
    id          TEXT        PRIMARY KEY,
    topic       TEXT        NOT NULL,
    subtopic    TEXT        NOT NULL,
    difficulty  TEXT        NOT NULL CHECK (difficulty IN ('easy', 'medium', 'hard')),
    prompt      TEXT        NOT NULL,
    solution    TEXT,
    test_cases  JSONB       NOT NULL DEFAULT '[]',
    source      TEXT        NOT NULL CHECK (source IN ('mbpp', 'apps', 'custom')),
    test_form   TEXT        CHECK (test_form IN ('pretest_pool', 'posttest_pool', 'practice_pool')),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Index for the selection query:
--   WHERE topic = ? AND difficulty = ? AND test_form = ?
CREATE INDEX IF NOT EXISTS idx_qb_topic_diff_form
    ON public.question_bank (topic, difficulty, test_form);

-- Index to speed up coverage / gap analysis queries by source
CREATE INDEX IF NOT EXISTS idx_qb_source
    ON public.question_bank (source);

-- RLS: read-only for authenticated students (served by API)
ALTER TABLE public.question_bank ENABLE ROW LEVEL SECURITY;

-- Authenticated users may read any question (question content is not sensitive)
CREATE POLICY IF NOT EXISTS "Authenticated users can read question bank"
    ON public.question_bank FOR SELECT
    TO authenticated
    USING (true);

-- Service role (used by ingest_question_bank.py) bypasses RLS automatically.
-- No explicit policy needed — Supabase service_role key ignores RLS.


-- ----------------------------------------------------------------------------
-- 2. asked_questions
--    Append-only log of every question served to a student.
--    Used by the selection query (NOT IN sub-select) to exclude already-seen
--    questions, guaranteeing no repeats per student across sessions.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.asked_questions (
    id          BIGSERIAL   PRIMARY KEY,
    student_id  TEXT        NOT NULL,
    question_id TEXT        NOT NULL REFERENCES public.question_bank(id) ON DELETE CASCADE,
    context     TEXT        NOT NULL CHECK (context IN ('pretest', 'posttest', 'practice')),
    correct     BOOLEAN,
    asked_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Primary lookup index: given a student_id, quickly find all seen question ids
CREATE INDEX IF NOT EXISTS idx_aq_student_id
    ON public.asked_questions (student_id);

-- Composite index for the NOT IN sub-select pattern
CREATE INDEX IF NOT EXISTS idx_aq_student_question
    ON public.asked_questions (student_id, question_id);

-- RLS: students read/write only their own rows
ALTER TABLE public.asked_questions ENABLE ROW LEVEL SECURITY;

-- Students can log questions they've been asked
CREATE POLICY IF NOT EXISTS "Students can insert own asked questions"
    ON public.asked_questions FOR INSERT
    TO authenticated
    WITH CHECK (student_id = (
        SELECT up.student_id
        FROM public.user_profiles up
        WHERE up.id = auth.uid()
    ));

-- Students can read their own history
CREATE POLICY IF NOT EXISTS "Students can read own asked questions"
    ON public.asked_questions FOR SELECT
    TO authenticated
    USING (student_id = (
        SELECT up.student_id
        FROM public.user_profiles up
        WHERE up.id = auth.uid()
    ));

-- Students can update correct/incorrect result for their own rows
CREATE POLICY IF NOT EXISTS "Students can update own asked questions"
    ON public.asked_questions FOR UPDATE
    TO authenticated
    USING (student_id = (
        SELECT up.student_id
        FROM public.user_profiles up
        WHERE up.id = auth.uid()
    ));


-- ============================================================================
-- CANONICAL SELECTION QUERY
-- ============================================================================
-- Use this pattern in the API when serving a question to a student.
-- Replace :topic, :difficulty, :pool_for_context, :student_id with bindings.
--
--   :pool_for_context is one of:
--       'pretest_pool'  when context = 'pretest'
--       'posttest_pool' when context = 'posttest'
--       'practice_pool' when context = 'practice'
--
-- SELECT *
-- FROM   public.question_bank
-- WHERE  topic       = :topic
--   AND  difficulty  = :difficulty
--   AND  test_form   = :pool_for_context
--   AND  id NOT IN (
--            SELECT question_id
--            FROM   public.asked_questions
--            WHERE  student_id = :student_id
--        )
-- ORDER BY random()
-- LIMIT 1;
-- ============================================================================

-- ============================================================================
-- COVERAGE GAP REFERENCE
-- ============================================================================
-- Run this query after ingestion to check which (topic, difficulty) buckets
-- have fewer than 10 questions per pool (minimum for a semester without repeats):
--
-- SELECT topic, difficulty, test_form, count(*) AS n,
--        CASE WHEN count(*) < 10 THEN '⚠ BELOW THRESHOLD' ELSE 'ok' END AS status
-- FROM   public.question_bank
-- GROUP  BY topic, difficulty, test_form
-- ORDER  BY topic, difficulty, test_form;
-- ============================================================================

-- Done
