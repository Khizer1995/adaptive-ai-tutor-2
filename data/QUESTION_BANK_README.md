# Question Bank — MCQ Bank (Array · Queue · Graph)

This document describes the **new MCQ-only question bank** used by the
Cognitive Adaptive AI Tutor for pre-test, post-test, and practice quizzes.

> **Status**: Bank is currently empty (rebuilt October 2026).
> New MCQ JSON batches are being ingested — see ingest instructions below.

---

## 1. Topics Covered

| Topic | Difficulty levels |
|-------|------------------|
| **Array** | easy · medium · hard |
| **Queue** | easy · medium · hard |
| **Graph** | easy · medium · hard |

---

## 2. Schema

Each item in the JSON batch follows this schema:

```json
{
  "id":            "string, unique (e.g. mcq_arr_easy_001)",
  "topic":         "Array | Queue | Graph",
  "subtopic":      "string, curriculum subtopic",
  "difficulty":    "easy | medium | hard",
  "question_type": "mcq",
  "prompt":        "string, the question text",
  "options":       ["option A", "option B", "option C", "option D"],
  "correct_index": 0,
  "explanation":   "string, why the correct answer is correct",
  "distractor_tags": [null, "tag_b", "tag_c", "tag_d"],
  "concept":       "string, concept group id (used for pool split)",
  "form":          "a | b | null"
}
```

`concept` + `form` control the **pretest/posttest/practice pool assignment** —
see [`SPLIT_RULE.md`](SPLIT_RULE.md) for the full rule.

---

## 3. Pool Split Rule

See **[`data/SPLIT_RULE.md`](SPLIT_RULE.md)** for the canonical split rule.

Summary:
- `form="a"` for a concept → `pretest_pool`
- `form="b"` for the same concept → `posttest_pool`
- All other items → `practice_pool`
- Items without a `concept` field → `practice_pool`

---

## 4. Ingest Instructions

> Instructions will be added here once the new ingest script is written.

```bash
# Preview (no DB writes)
python scripts/ingest_mcq_bank.py --dry-run

# Ingest into Supabase (requires SUPABASE_URL + SUPABASE_SERVICE_KEY in .env)
python scripts/ingest_mcq_bank.py
```

The `question_bank` table already exists with the correct schema
(see `scripts/migration_question_bank.sql` + `scripts/migration_mcq_columns.sql`).

---

## 5. No-Repetition Selection

Per-student question tracking is handled by the `asked_questions` table.
Once a question is served to a student, it is logged and excluded from
future draws for that student.

---

*Previous MBPP/APPS/custom bank (1,043 rows) was removed on 2026-10-10.*
*Split rule for the old code-item bank is preserved in [`SPLIT_RULE.md`](SPLIT_RULE.md).*
