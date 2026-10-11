#!/usr/bin/env python3
"""
scripts/ingest_mcq_bank.py
==========================
Ingests the 9 MCQ JSON files into Supabase question_bank.

Usage
-----
  # Dry-run (validate + split, no DB writes):
  python scripts/ingest_mcq_bank.py --dry-run

  # Run individual stages:
  python scripts/ingest_mcq_bank.py --stage validate
  python scripts/ingest_mcq_bank.py --stage split
  python scripts/ingest_mcq_bank.py --stage write    # requires approval

  # Full pipeline without DB write:
  python scripts/ingest_mcq_bank.py --stage validate --stage split

Design
------
  Split rule (40/40/20, seed=42):
    Within each (topic × difficulty) group of 40 questions:
      indices [0:16]  → test_form = 'pretest_pool'
      indices [16:32] → test_form = 'posttest_pool'
      indices [32:40] → test_form = 'practice_pool'
    The shuffle uses a FIXED random seed so every re-run produces the
    same assignment.  Pretest and posttest are disjoint by construction.

  Upsert:
    Upserts 100 rows/chunk on id (PK).  Re-running is safe and idempotent.

  Intermediate output:
    data/mcq_bank_merged.json  — all 360 rows with test_form assigned.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data" / "mcq"
MERGED_OUTPUT = REPO_ROOT / "data" / "mcq_bank_merged.json"

RANDOM_SEED = 42
CHUNK_SIZE = 100

REQUIRED_FIELDS = {
    "id", "topic", "subtopic", "difficulty",
    "prompt", "options", "correct_index", "explanation", "source",
}

MCQ_FILES = [
    DATA_DIR / "mcq_ar_easy.json",
    DATA_DIR / "mcq_ar_medium.json",
    DATA_DIR / "mcq_ar_hard.json",
    DATA_DIR / "mcq_qu_easy.json",
    DATA_DIR / "mcq_qu_medium.json",
    DATA_DIR / "mcq_qu_hard.json",
    DATA_DIR / "mcq_gr_easy.json",
    DATA_DIR / "mcq_gr_medium.json",
    DATA_DIR / "mcq_gr_hard.json",
]

# Expected questions per file
EXPECTED_PER_FILE = 40

# Pool assignment sizes (must sum to EXPECTED_PER_FILE)
PRETEST_SIZE  = 16
POSTTEST_SIZE = 16
PRACTICE_SIZE = 8
assert PRETEST_SIZE + POSTTEST_SIZE + PRACTICE_SIZE == EXPECTED_PER_FILE


# ---------------------------------------------------------------------------
# Stage 1 — Validate
# ---------------------------------------------------------------------------

def validate(files: list[Path], verbose: bool = True) -> list[list[dict]]:
    """
    Structural validation.  Fails loudly (sys.exit(1)) on any error.
    Returns: list of per-file question lists.
    """
    errors: list[str] = []
    all_files_data: list[list[dict]] = []
    all_ids: set[str] = set()

    for path in files:
        if not path.exists():
            errors.append(f"MISSING FILE: {path}")
            all_files_data.append([])
            continue

        try:
            data: list[dict] = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"JSON PARSE ERROR {path.name}: {exc}")
            all_files_data.append([])
            continue

        if not isinstance(data, list):
            errors.append(f"{path.name}: root must be a JSON array")
            all_files_data.append([])
            continue

        n = len(data)
        if n != EXPECTED_PER_FILE:
            errors.append(f"{path.name}: expected {EXPECTED_PER_FILE} items, got {n}")

        for i, item in enumerate(data):
            loc = f"{path.name}[{i}]"
            if not isinstance(item, dict):
                errors.append(f"{loc}: item is not a dict")
                continue
            missing = REQUIRED_FIELDS - set(item.keys())
            if missing:
                errors.append(f"{loc}: missing fields {sorted(missing)}")
            opts = item.get("options")
            if not isinstance(opts, list) or len(opts) != 4:
                errors.append(f"{loc}: options must be a list of exactly 4 strings")
            elif not all(isinstance(o, str) for o in opts):
                errors.append(f"{loc}: all options must be strings")
            ci = item.get("correct_index")
            if ci not in (0, 1, 2, 3):
                errors.append(f"{loc}: correct_index={ci!r} not in [0,1,2,3]")
            if item.get("source") != "custom_mcq":
                errors.append(f"{loc}: source={item.get('source')!r}, expected 'custom_mcq'")
            qid = item.get("id")
            if not qid:
                errors.append(f"{loc}: id is empty")
            elif qid in all_ids:
                errors.append(f"{loc}: duplicate id {qid!r}")
            else:
                all_ids.add(qid)

        if verbose and not errors:
            first = data[0] if data else {}
            print(
                f"  OK  {path.name}: {n} items  "
                f"topic={first.get('topic')!r}  difficulty={first.get('difficulty')!r}"
            )
        all_files_data.append(data)

    if errors:
        print("\nVALIDATION ERRORS:")
        for e in errors:
            print(f"  [X] {e}")
        sys.exit(1)

    total = sum(len(d) for d in all_files_data)
    print(f"\nValidation passed: {len(files)} files, {total} questions, 0 errors.")
    return all_files_data


# ---------------------------------------------------------------------------
# Stage 2 — Split
# ---------------------------------------------------------------------------

def split(all_files_data: list[list[dict]]) -> list[dict]:
    """
    For each (topic × difficulty) group of 40:
      - Shuffle with fixed seed=42.
      - Assign test_form: pretest_pool[0:16], posttest_pool[16:32], practice_pool[32:40].
    Returns merged list of all 360 enriched question dicts.
    """
    merged: list[dict] = []

    # Group by (topic, difficulty) preserving file order
    groups: dict[tuple[str, str], list[dict]] = {}
    for file_data in all_files_data:
        for q in file_data:
            key = (q["topic"], q["difficulty"])
            groups.setdefault(key, []).append(q)

    pool_counts: dict[tuple[str, str], dict[str, int]] = {}

    for (topic, difficulty), questions in groups.items():
        rng = random.Random(RANDOM_SEED)
        shuffled = questions[:]
        rng.shuffle(shuffled)

        pretest  = shuffled[:PRETEST_SIZE]
        posttest = shuffled[PRETEST_SIZE : PRETEST_SIZE + POSTTEST_SIZE]
        practice = shuffled[PRETEST_SIZE + POSTTEST_SIZE :]

        assert len(practice) == PRACTICE_SIZE, \
            f"Practice pool size mismatch for ({topic},{difficulty}): {len(practice)}"

        # Verify disjointness
        pretest_ids  = {q["id"] for q in pretest}
        posttest_ids = {q["id"] for q in posttest}
        assert not pretest_ids & posttest_ids, \
            f"Pretest/posttest overlap for ({topic},{difficulty})!"

        pool_counts[(topic, difficulty)] = {
            "pretest_pool":  len(pretest),
            "posttest_pool": len(posttest),
            "practice_pool": len(practice),
        }

        for q in pretest:
            merged.append({**q, "test_form": "pretest_pool"})
        for q in posttest:
            merged.append({**q, "test_form": "posttest_pool"})
        for q in practice:
            merged.append({**q, "test_form": "practice_pool"})

    return merged, pool_counts


# ---------------------------------------------------------------------------
# Stage 3 — Write (upsert to Supabase)
# ---------------------------------------------------------------------------

def write(merged: list[dict], dry_run: bool = False) -> None:
    """
    Batch upsert 100 rows/chunk, on_conflict='id'.
    Idempotent: re-running never duplicates or changes test_form assignments.
    """
    if dry_run:
        print(f"\n[DRY-RUN] Would upsert {len(merged)} rows to question_bank "
              f"in {-(-len(merged) // CHUNK_SIZE)} chunks of {CHUNK_SIZE}. "
              "Skipping DB writes.")
        return

    # Import here so validate/split stages work without Supabase credentials.
    import os
    from dotenv import load_dotenv
    load_dotenv(REPO_ROOT / ".env")

    from supabase import create_client

    url = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
    svc_key = os.getenv("SUPABASE_SERVICE_KEY", "").strip()
    if not url or not svc_key:
        print("ERROR: SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in .env")
        sys.exit(1)

    sb = create_client(url, svc_key)

    # Build DB row from question dict (keep only columns the table knows)
    def to_db_row(q: dict) -> dict:
        return {
            "id":            q["id"],
            "topic":         q["topic"],
            "subtopic":      q["subtopic"],
            "difficulty":    q["difficulty"],
            "prompt":        q["prompt"],
            "options":       q["options"],        # list[str] → Supabase stores as jsonb
            "correct_index": q["correct_index"],
            "explanation":   q["explanation"],
            "source":        q["source"],          # "custom_mcq"
            "test_form":     q["test_form"],
            "question_type": "mcq",
            # solution and test_cases are intentionally omitted (nullable)
        }

    rows = [to_db_row(q) for q in merged]
    total = len(rows)
    inserted = 0

    for i in range(0, total, CHUNK_SIZE):
        chunk = rows[i : i + CHUNK_SIZE]
        sb.table("question_bank").upsert(chunk, on_conflict="id").execute()
        inserted += len(chunk)
        print(f"  Upserted {inserted}/{total} rows...")

    print(f"\nWrite complete: {inserted} rows upserted to question_bank.")


# ---------------------------------------------------------------------------
# Dry-run reporting
# ---------------------------------------------------------------------------

def print_dry_run_report(
    all_files_data: list[list[dict]],
    merged: list[dict],
    pool_counts: dict[tuple[str, str], dict[str, int]],
) -> None:
    print("\n" + "=" * 60)
    print("DRY-RUN REPORT")
    print("=" * 60)

    print("\nPer-file counts:")
    for path, file_data in zip(MCQ_FILES, all_files_data):
        first = file_data[0] if file_data else {}
        print(
            f"  {path.name}: {len(file_data)} items  "
            f"[topic={first.get('topic')!r}, diff={first.get('difficulty')!r}]"
        )
        print(f"    First item id: {first.get('id')!r}")

    print(f"\nTotal items: {len(merged)}")

    print("\nPer-cell pool counts (must be 16/16/8 for each):")
    header = f"  {'Topic':<10} {'Difficulty':<10} {'pretest':>8} {'posttest':>9} {'practice':>9}  Status"
    print(header)
    print("  " + "-" * 56)
    all_ok = True
    for (topic, difficulty), counts in sorted(pool_counts.items()):
        pre  = counts["pretest_pool"]
        post = counts["posttest_pool"]
        prac = counts["practice_pool"]
        ok = (pre == PRETEST_SIZE and post == POSTTEST_SIZE and prac == PRACTICE_SIZE)
        if not ok:
            all_ok = False
        status = "[OK]" if ok else f"[FAIL] expected {PRETEST_SIZE}/{POSTTEST_SIZE}/{PRACTICE_SIZE}"
        print(f"  {topic:<10} {difficulty:<10} {pre:>8} {post:>9} {prac:>9}  {status}")

    totals = {"pretest_pool": 0, "posttest_pool": 0, "practice_pool": 0}
    for counts in pool_counts.values():
        for k, v in counts.items():
            totals[k] += v
    print(f"  {'TOTAL':<10} {'':<10} {totals['pretest_pool']:>8} "
          f"{totals['posttest_pool']:>9} {totals['practice_pool']:>9}")
    print(f"  Expected:               144       144        72")

    if all_ok:
        print("\n[PASS] All cells: 16 pretest / 16 posttest / 8 practice. Split verified.")
    else:
        print("\n[FAIL] Some cells have wrong pool sizes. Check split logic.")
        sys.exit(1)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ingest MCQ bank into Supabase question_bank table."
    )
    parser.add_argument(
        "--stage",
        action="append",
        choices=["validate", "split", "write"],
        dest="stages",
        help="Stage(s) to run. If omitted with --dry-run, runs all stages except write.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and split, print report, NO DB writes.",
    )
    args = parser.parse_args()

    stages = args.stages or []
    dry_run = args.dry_run

    # Default: dry-run runs validate + split + report (no write)
    if dry_run and not stages:
        stages = ["validate", "split"]

    # Default: if no stages and no dry-run, run all
    if not stages and not dry_run:
        stages = ["validate", "split", "write"]

    print("MCQ Bank Ingest")
    print("=" * 40)
    print(f"Stages : {stages}")
    print(f"Dry-run: {dry_run}")
    print(f"Files  : {len(MCQ_FILES)}")
    print()

    all_files_data: list[list[dict]] = []
    merged: list[dict] = []
    pool_counts: dict = {}

    if "validate" in stages:
        print("-- Stage 1: Validate --")
        all_files_data = validate(MCQ_FILES)

    if "split" in stages:
        if not all_files_data:
            print("-- Stage 1: Validate (required for split) --")
            all_files_data = validate(MCQ_FILES)
        print("\n-- Stage 2: Split --")
        merged, pool_counts = split(all_files_data)

        # Write merged JSON (intermediate artifact -- always, even on dry-run)
        MERGED_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        MERGED_OUTPUT.write_text(
            json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"Intermediate merged JSON written to: {MERGED_OUTPUT}")
        print(f"Total rows: {len(merged)}")

    if dry_run:
        if not all_files_data or not merged:
            print("WARNING: --dry-run needs validate+split stages. Re-running them now.")
            all_files_data = validate(MCQ_FILES)
            merged, pool_counts = split(all_files_data)
        print_dry_run_report(all_files_data, merged, pool_counts)
        print("\n[DRY-RUN] No DB writes performed.")
        return

    if "write" in stages:
        if not merged:
            print("-- Stage 1+2: Validate + Split (required for write) --")
            all_files_data = validate(MCQ_FILES)
            merged, pool_counts = split(all_files_data)
        print("\n-- Stage 3: Write --")
        write(merged, dry_run=False)

    print("\nDone.")


if __name__ == "__main__":
    main()
