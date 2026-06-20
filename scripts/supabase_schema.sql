-- ============================================================================
-- Cognitive Adaptive AI Tutor — Supabase Schema
-- ============================================================================
-- Run this entire script in the Supabase SQL Editor:
--   Dashboard → SQL Editor → New Query → Paste → Run
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 1. user_profiles
--    One row per authenticated user.  id = auth.uid() (UUID from Supabase Auth)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.user_profiles (
    id              UUID        PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    student_id      TEXT        UNIQUE NOT NULL,   -- "USER-<first8 of uuid>"
    full_name       TEXT        NOT NULL DEFAULT '',
    email           TEXT        NOT NULL DEFAULT '',
    level           TEXT        NOT NULL DEFAULT 'beginner',   -- beginner|intermediate|advanced
    subject         TEXT        NOT NULL DEFAULT 'dsa',
    learning_style  TEXT        NOT NULL DEFAULT 'balanced',   -- visual|balanced|problem-solver
    current_topic   TEXT,
    current_subtopic TEXT,
    engagement      TEXT        NOT NULL DEFAULT 'medium',
    last_score      FLOAT       NOT NULL DEFAULT 0.0,
    frustration_level INT       NOT NULL DEFAULT 0,
    engagement_score  INT       NOT NULL DEFAULT 5,
    learning_gain   FLOAT       NOT NULL DEFAULT 0.0,
    normalized_learning_gain FLOAT NOT NULL DEFAULT 0.0,
    pretest_score   FLOAT,
    posttest_score  FLOAT,
    last_assessment_type TEXT,
    last_active     TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- RLS
ALTER TABLE public.user_profiles ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can read own profile"
    ON public.user_profiles FOR SELECT
    USING (auth.uid() = id);

CREATE POLICY "Users can insert own profile"
    ON public.user_profiles FOR INSERT
    WITH CHECK (auth.uid() = id);

CREATE POLICY "Users can update own profile"
    ON public.user_profiles FOR UPDATE
    USING (auth.uid() = id);

-- ----------------------------------------------------------------------------
-- 2. learning_history
--    Append-only record of every quiz/assessment attempt.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.learning_history (
    id              BIGSERIAL   PRIMARY KEY,
    user_id         UUID        NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    student_id      TEXT        NOT NULL,
    topic           TEXT        NOT NULL,
    subtopic        TEXT,
    record_type     TEXT        NOT NULL DEFAULT 'quiz',  -- quiz|pretest|posttest
    score           FLOAT       NOT NULL DEFAULT 0.0,
    question_count  INT         NOT NULL DEFAULT 0,
    passed          BOOLEAN     NOT NULL DEFAULT FALSE,
    recorded_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_learning_history_user_id
    ON public.learning_history(user_id);
CREATE INDEX IF NOT EXISTS idx_learning_history_topic
    ON public.learning_history(user_id, topic);

-- RLS
ALTER TABLE public.learning_history ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can read own learning history"
    ON public.learning_history FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own learning history"
    ON public.learning_history FOR INSERT
    WITH CHECK (auth.uid() = user_id);

-- ----------------------------------------------------------------------------
-- 3. knowledge_states
--    JSONB snapshot of the student's full knowledge_state dict.
--    Upserted on every quiz submit / profile save.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.knowledge_states (
    id              BIGSERIAL   PRIMARY KEY,
    user_id         UUID        UNIQUE NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    student_id      TEXT        NOT NULL,
    state_blob      JSONB       NOT NULL DEFAULT '{}',
    progress        JSONB       NOT NULL DEFAULT '[]',   -- list of mastered topics
    knowledge_events JSONB      NOT NULL DEFAULT '[]',
    delivered_chunks JSONB      NOT NULL DEFAULT '{}',
    quiz_seen_questions JSONB   NOT NULL DEFAULT '{}',
    subtopic_mastery JSONB      NOT NULL DEFAULT '{}',
    subtopic_progress JSONB     NOT NULL DEFAULT '{}',
    weak_areas      JSONB       NOT NULL DEFAULT '{}',
    strong_areas    JSONB       NOT NULL DEFAULT '{}',
    quiz_attempts   JSONB       NOT NULL DEFAULT '{}',
    assessment_scores JSONB     NOT NULL DEFAULT '{}',
    assessment_history JSONB    NOT NULL DEFAULT '[]',
    accuracy_history JSONB      NOT NULL DEFAULT '[]',
    learning_gain_history JSONB NOT NULL DEFAULT '[]',
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- RLS
ALTER TABLE public.knowledge_states ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can read own knowledge state"
    ON public.knowledge_states FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own knowledge state"
    ON public.knowledge_states FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own knowledge state"
    ON public.knowledge_states FOR UPDATE
    USING (auth.uid() = user_id);

-- ----------------------------------------------------------------------------
-- 4. survey_responses
--    Stores post-session Likert survey data.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.survey_responses (
    id              BIGSERIAL   PRIMARY KEY,
    user_id         UUID        NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    student_id      TEXT        NOT NULL,
    topic           TEXT,
    subtopic        TEXT,
    responses       JSONB       NOT NULL DEFAULT '{}',
    open_text       JSONB       NOT NULL DEFAULT '{}',
    recorded_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- RLS
ALTER TABLE public.survey_responses ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can read own survey responses"
    ON public.survey_responses FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own survey responses"
    ON public.survey_responses FOR INSERT
    WITH CHECK (auth.uid() = user_id);

-- ----------------------------------------------------------------------------
-- 5. Trigger: auto-update updated_at timestamp on user_profiles
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_user_profiles_updated_at ON public.user_profiles;
CREATE TRIGGER trigger_user_profiles_updated_at
    BEFORE UPDATE ON public.user_profiles
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

DROP TRIGGER IF EXISTS trigger_knowledge_states_updated_at ON public.knowledge_states;
CREATE TRIGGER trigger_knowledge_states_updated_at
    BEFORE UPDATE ON public.knowledge_states
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- ----------------------------------------------------------------------------
-- DONE — All tables created with RLS enabled.
-- ============================================================================
