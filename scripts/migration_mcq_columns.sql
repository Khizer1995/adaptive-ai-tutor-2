-- scripts/migration_mcq_columns.sql
-- =====================================================================
-- MCQ Bank Migration — Idempotent DDL Guards
-- Run in Supabase SQL Editor BEFORE executing the ingest script.
-- Safe to re-run: every statement uses IF NOT EXISTS / IF EXISTS guards.
-- =====================================================================

-- ── 1. MCQ columns (all already present per pre-check — no-ops) ──────

ALTER TABLE question_bank
  ADD COLUMN IF NOT EXISTS question_type text
    NOT NULL DEFAULT 'mcq'
    CHECK (question_type IN ('mcq', 'code'));

ALTER TABLE question_bank
  ADD COLUMN IF NOT EXISTS options jsonb;

ALTER TABLE question_bank
  ADD COLUMN IF NOT EXISTS correct_index int
    CHECK (correct_index BETWEEN 0 AND 3);

ALTER TABLE question_bank
  ADD COLUMN IF NOT EXISTS explanation text;

-- ── 2. Drop NOT NULL on legacy code-question columns (if set) ─────────
-- Makes solution / test_cases optional so MCQ rows can omit them.

ALTER TABLE question_bank
  ALTER COLUMN solution     DROP NOT NULL;

ALTER TABLE question_bank
  ALTER COLUMN test_cases   DROP NOT NULL;

-- ── 3. Extend the source CHECK to include 'custom_mcq' ───────────────
-- CRITICAL: the existing constraint only allows 'mbpp'/'apps'/'custom'.
-- Without this, every MCQ ingest row will fail with a CHECK violation.

ALTER TABLE question_bank
  DROP CONSTRAINT IF EXISTS question_bank_source_check;

ALTER TABLE question_bank
  ADD CONSTRAINT question_bank_source_check
    CHECK (source IN ('mbpp', 'apps', 'custom', 'custom_mcq'));

-- ── 4. Confirm test_form CHECK covers all three pool names ────────────
-- (Idempotent: if constraint already has these values this is a no-op.)

ALTER TABLE question_bank
  DROP CONSTRAINT IF EXISTS question_bank_test_form_check;

ALTER TABLE question_bank
  ADD CONSTRAINT question_bank_test_form_check
    CHECK (test_form IN ('pretest_pool', 'posttest_pool', 'practice_pool'));

-- ── 5. asked_questions.correct is already nullable — confirm only ─────
-- No DDL needed; verified via live probe (INSERT correct=NULL succeeded).
-- Documenting here for clarity:
--   asked_questions.correct  boolean  NULL => question shown, not yet graded
--                                     TRUE  => student answered correctly
--                                     FALSE => student answered incorrectly

-- ── Done ──────────────────────────────────────────────────────────────
-- After running this SQL, execute:
--   python scripts/ingest_mcq_bank.py --stage validate --dry-run
--   python scripts/ingest_mcq_bank.py --stage split   --dry-run
--   python scripts/ingest_mcq_bank.py --dry-run          (all stages)
-- Then, on explicit approval:
--   python scripts/ingest_mcq_bank.py --stage write
