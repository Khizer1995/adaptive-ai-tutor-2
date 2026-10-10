# Question Bank — Sources, Methods & Coverage

This document describes `data/question_bank_normalized.json` — the unified question pool used by the Cognitive Adaptive AI Tutor for pre-test, post-test, and practice quizzes.

---

## 1. Dataset Sources

| Source | Dataset ID | License | Items fetched | Items in bank |
|--------|-----------|---------|--------------|---------------|
| **MBPP** | [`google-research-datasets/mbpp`](https://huggingface.co/datasets/google-research-datasets/mbpp) (`full` split) | CC-BY-4.0 | ~374 | varies (see coverage report) |
| **APPS** | [`codeparrot/apps`](https://huggingface.co/datasets/codeparrot/apps) (`all` split, `introductory` + `interview` only) | MIT | ~5 000 (sampled 500) | varies |
| **Custom** | Authored by project team | Project IP | 20 | 20 |

> **APPS sampling rationale**: The full APPS dataset contains ~10 000 items, the majority at "competition" difficulty — primarily DP and graph problems that require competitive-programming-level optimization and don't map to our 7-topic curriculum. Only `introductory` and `interview` difficulty items are included, and a random sample of 500 is classified to control API quota.

---

## 2. Schema

Each item in `question_bank_normalized.json` follows this schema:

```json
{
  "id":         "string, unique (e.g. mbpp_1, apps_4327, custom_ll_001)",
  "topic":      "Array | Linked List | Stack | Queue | Hash Table | Tree | Graph",
  "subtopic":   "string, one of the 48 curriculum subtopics",
  "difficulty": "easy | medium | hard",
  "prompt":     "string, the question/problem statement",
  "solution":   "string, reference solution code",
  "test_cases": ["list of assert statements or input/output pairs"],
  "source":     "mbpp | apps | custom",
  "test_form":  "pretest_pool | posttest_pool | practice_pool"
}
```

---

## 3. Topic Classification Method (MBPP / APPS)

Neither MBPP nor APPS ships with DSA topic or subtopic tags. A **one-time LLM classification pass** was performed using **Gemini 1.5 Flash** to assign each item a `topic`, `subtopic`, and `difficulty` from the curriculum taxonomy.

Key implementation details:
- Results are **cached** in `data/raw/classification_cache.json` — reruns cost nothing.
- Items where no curriculum topic applies (pure math, string formatting, etc.) are **excluded** from the bank and logged.
- The classification prompt enforces the exact 7-topic / 48-subtopic taxonomy from `core/curriculum_config.py`.
- APPS difficulty metadata (`introductory → easy`, `interview → medium`, `competition → hard`) overrides LLM difficulty for APPS items.

To re-run classification or expand the sample:
```bash
python scripts/build_question_bank.py --stage classify --apps-sample 1000 --verbose
```

---

## 4. Pre-test / Post-test Pool Split

Within each `(topic, difficulty)` cell, questions are shuffled with a fixed random seed (42) and split **50/50**:

- First half → `pretest_pool`
- Second half → `posttest_pool`
- Odd remainder → `practice_pool`

This guarantees **structurally disjoint** pre-test and post-test items, fixing the test-retest validity issue where identical items were served in both assessments (invalidating measured learning gain).

`practice_pool` questions are served during in-session practice and can repeat across contexts but not per-student (tracked via `asked_questions` table).

---

## 5. Custom-Authored Questions — Rationale

MBPP and APPS are judge/benchmark-style datasets requiring stdin/stdout submission. They poorly represent **pointer- and structure-heavy** topics that don't map cleanly to that format. The following subtopics are confirmed weak-to-absent in both datasets and were custom-authored:

| Topic | Missing Subtopics | Custom IDs |
|-------|------------------|-----------|
| **Linked List** | Insertion Operations, Deletion Operations, Traversal & Search, Doubly Linked List, Circular Linked List | `custom_ll_001` – `custom_ll_005` |
| **Queue** | Enqueue, Dequeue, Circular Queue, Deque | `custom_q_001` – `custom_q_004` |
| **Stack** | Stack using Array, Stack using Linked List, Applications | `custom_st_001` – `custom_st_003` |
| **Hash Table** | Hash Functions, Collision: Chaining, Collision: Open Addressing | `custom_hash_001` – `custom_hash_003` |
| **Tree** | BST Operations, Tree Traversal, Balanced Trees (AVL/RB) | `custom_tree_001` – `custom_tree_004` |

All 20 custom items include a reference solution and at least one `assert`-style test case. They were pre-validated by the authors.

> **Note**: Priority Queue (via heap problems) and Stack applications (expression evaluation) **are** covered by APPS and MBPP respectively — only the structural implementation subtopics are custom.

---

## 6. Coverage Gap Report

Run the build script to generate an up-to-date report:

```bash
python scripts/build_question_bank.py --stage all
```

The script flags any `(topic, difficulty, test_form)` combination with **fewer than 10 questions** — the minimum to sustain non-repetition across a full semester (assuming 2 assessments × 5 questions = 10 draws per tier).

**Known gaps (custom questions only, before MBPP/APPS ingestion):**

| Topic | Difficulty | Notes |
|-------|-----------|-------|
| Linked List | easy, medium, hard | 1–2 custom items per tier; MBPP adds very few |
| Queue | easy, medium | 1–2 custom per tier |
| Stack | easy, medium | 1–3 custom per tier |
| Hash Table | easy, medium, hard | 1 custom per tier |
| Tree (Balanced) | hard | 2 custom items total |

After MBPP/APPS classification, Array and Graph topics should reach the threshold easily (both datasets have strong coverage of array manipulation and graph traversal). Structural topics (Linked List, Queue, Stack implementation, Hash mechanism, Tree balancing) will remain below threshold and should be supplemented with additional custom questions if needed.

**Recommended action**: Add at least 8 more custom questions per flagged `(topic, difficulty)` pair, prioritising `hard` tier for Linked List, Hash Table, and Tree.

---

## 7. Rebuild Instructions

```bash
# Install dependencies (once)
pip install datasets google-generativeai tqdm

# Full pipeline (first run — downloads datasets, classifies, splits, writes JSON)
python scripts/build_question_bank.py --stage all

# Preview what would be ingested (no DB writes)
python scripts/ingest_question_bank.py --dry-run

# Ingest into Supabase (requires SUPABASE_URL + SUPABASE_SERVICE_KEY in .env)
python scripts/ingest_question_bank.py
```

Run the SQL migration **before** ingesting:
```
Supabase Dashboard → SQL Editor → New Query → paste scripts/migration_question_bank.sql → Run
```

---

## 8. No-Repetition Selection Query

The API should use this pattern when serving a question:

```sql
SELECT *
FROM   public.question_bank
WHERE  topic       = :topic
  AND  difficulty  = :difficulty
  AND  test_form   = :pool_for_context   -- 'pretest_pool' | 'posttest_pool' | 'practice_pool'
  AND  id NOT IN (
           SELECT question_id
           FROM   public.asked_questions
           WHERE  student_id = :student_id
       )
ORDER BY random()
LIMIT 1;
```

After serving a question, insert a row into `asked_questions`:

```sql
INSERT INTO public.asked_questions (student_id, question_id, context)
VALUES (:student_id, :question_id, :context);
```

Update `correct` when the student submits their answer:

```sql
UPDATE public.asked_questions
SET    correct = :was_correct
WHERE  student_id = :student_id AND question_id = :question_id;
```
