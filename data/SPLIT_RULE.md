# Pool Split Rule — question_bank `test_form` Assignment

> **Purpose**: This document preserves the exact pool-assignment rules from
> the now-deleted `scripts/build_question_bank.py` so the new MCQ ingest
> script can re-implement them identically.
>
> The new MCQ bank covers **Array, Queue, Graph** only, and all items are
> MCQ type. Only the **MCQ split rule** (below) applies. The code-item
> 40/40/20 rule is preserved for reference in case code questions are added
> later.

---

## Rule 1 — MCQ items: `concept` + `form` fields (PRIMARY RULE for new bank)

Each MCQ item in the source JSON must carry two optional fields:

| Field | Values | Meaning |
|-------|--------|---------|
| `concept` | string (e.g. `"array_traversal"`) | Groups items that test the same concept |
| `form` | `"a"`, `"b"`, or `null`/omitted | Distinguishes pre/posttest variants |

**Assignment logic** (applied per concept group):

```
For each concept group:
  - The first item with form="a"  → test_form = "pretest_pool"
  - The first item with form="b"  → test_form = "posttest_pool"
  - All remaining items (no form, or extra a/b beyond the first) → test_form = "practice_pool"

Items with no concept at all → test_form = "practice_pool" (unconditionally)
```

**Invariant**: `form="a"` and `form="b"` items for the same concept **never** share a pool. This guarantees that a student's pretest and posttest items are structurally disjoint.

### Python reference implementation

```python
def split_mcq_items(mcq_items: list[dict]) -> list[dict]:
    """
    Assign test_form to MCQ items using concept + form fields.
    Mutates items in-place. Returns the same list.
    """
    # concept -> {"a": item|None, "b": item|None, "extra": [item, ...]}
    concept_map: dict[str, dict] = {}
    no_concept: list[dict] = []

    for item in mcq_items:
        concept = item.get("concept")
        form    = item.get("form")
        if not concept:
            item["test_form"] = "practice_pool"
            no_concept.append(item)
            continue
        if concept not in concept_map:
            concept_map[concept] = {"a": None, "b": None, "extra": []}
        if form == "a" and concept_map[concept]["a"] is None:
            concept_map[concept]["a"] = item
        elif form == "b" and concept_map[concept]["b"] is None:
            concept_map[concept]["b"] = item
        else:
            concept_map[concept]["extra"].append(item)

    for concept, slots in concept_map.items():
        if slots["a"]:
            slots["a"]["test_form"] = "pretest_pool"
        if slots["b"]:
            slots["b"]["test_form"] = "posttest_pool"
        for extra in slots["extra"]:
            extra["test_form"] = "practice_pool"

    return mcq_items
```

---

## Rule 2 — Code items: 40/40/20 per `(topic, difficulty)` group (LEGACY, preserved for reference)

> This rule applied to MBPP/APPS/custom **code** items in the old bank.
> Not applicable to the new MCQ-only bank unless code questions are added.

**Assignment logic**:

```
For each (topic, difficulty) group:
  1. Shuffle the group with random seed 42.
  2. pre_n  = int(n * 0.40)   ← first 40%  → pretest_pool
  3. post_n = int(n * 0.40)   ← next  40%  → posttest_pool
  4. remainder               ← last  ~20% → practice_pool
```

**Properties**:
- Pretest and posttest pools are **disjoint by construction** (different index ranges from the same shuffle).
- The 20% practice pool is the tail; for small groups (n < 5) this may be 0 items.
- Seed 42 is fixed so re-running produces the same split (stable across rebuilds).
- A `pool_assignments.json` freeze file was used to keep existing rows' pool stable when adding new items.

### Python reference implementation

```python
import random
from collections import defaultdict

def split_code_items(code_items: list[dict], seed: int = 42) -> list[dict]:
    """
    Assign test_form to code items using 40/40/20 split per (topic, difficulty).
    Mutates items in-place. Returns the same list.
    """
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for q in code_items:
        key = (q.get("topic"), q.get("difficulty"))
        groups[key].append(q)

    rng = random.Random(seed)
    for (topic, diff), group in groups.items():
        rng.shuffle(group)
        n      = len(group)
        pre_n  = int(n * 0.40)
        post_n = int(n * 0.40)
        for i, q in enumerate(group):
            if i < pre_n:
                q["test_form"] = "pretest_pool"
            elif i < pre_n + post_n:
                q["test_form"] = "posttest_pool"
            else:
                q["test_form"] = "practice_pool"

    return code_items
```

---

## Pool → Context mapping (unchanged for new bank)

| `test_form` value | Used by endpoint | `context` value written to `asked_questions` |
|---|---|---|
| `pretest_pool` | `POST /quiz/pretest` | `"pretest"` |
| `posttest_pool` | `POST /quiz/posttest` | `"posttest"` |
| `practice_pool` | `POST /quiz/generate` | `"practice"` |

---

*Extracted from `scripts/build_question_bank.py` (functions `_split_mcq_items`,*
*`_split_code_items`, `stage_split`) on 2026-10-10 before that script was deleted.*
