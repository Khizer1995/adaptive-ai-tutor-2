"""
scripts/ingest_question_bank.py
================================
Loads data/question_bank_normalized.json into Supabase's public.question_bank
table via batch upsert.

Usage
-----
    # Preview what would be inserted (no writes):
    python scripts/ingest_question_bank.py --dry-run

    # Full ingest:
    python scripts/ingest_question_bank.py

    # Custom file path:
    python scripts/ingest_question_bank.py --file data/my_questions.json

    # Adjust batch size (default 100):
    python scripts/ingest_question_bank.py --chunk-size 50

Requirements
------------
    SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in .env
    (service key is required to bypass RLS during bulk ingest).

The script is idempotent: it uses upsert() so re-running after partial
failures is safe — existing rows are overwritten with the latest data.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_JSON  = PROJECT_ROOT / "data" / "question_bank_normalized.json"
TABLE_NAME    = "question_bank"

# Columns that exist in the DB table (used to strip extra keys from JSON)
VALID_COLUMNS = {
    "id", "topic", "subtopic", "difficulty",
    "prompt", "solution", "test_cases", "source", "test_form",
}


# ---------------------------------------------------------------------------
# Supabase client (service role — bypasses RLS)
# ---------------------------------------------------------------------------
def get_service_client() -> Client:
    url = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
    # Prefer SUPABASE_SERVICE_KEY; fall back to SUPABASE_KEY
    key = (
        os.getenv("SUPABASE_SERVICE_KEY", "").strip()
        or os.getenv("SUPABASE_KEY", "").strip()
    )
    if not url or not key:
        sys.exit(
            "ERROR: SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in .env\n"
            "       (service key is required to bypass RLS for bulk ingest)"
        )
    # Strip /rest/v1 if accidentally included
    if url.endswith("/rest/v1"):
        url = url[: -len("/rest/v1")]
    return create_client(url, key)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def load_questions(path: Path) -> list[dict]:
    if not path.exists():
        sys.exit(f"ERROR: File not found: {path}\n       Run build_question_bank.py first.")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        sys.exit("ERROR: JSON root must be an array of question objects.")
    return data


def sanitize(questions: list[dict]) -> list[dict]:
    """
    Ensure test_cases is a JSON-serialisable list (JSONB column),
    and strip any keys not in VALID_COLUMNS so the upsert doesn't reject them.
    """
    clean = []
    for q in questions:
        row = {k: v for k, v in q.items() if k in VALID_COLUMNS}
        # Ensure test_cases is always a list
        tc = row.get("test_cases", [])
        if isinstance(tc, str):
            try:
                tc = json.loads(tc)
            except json.JSONDecodeError:
                tc = [tc]
        row["test_cases"] = tc if isinstance(tc, list) else list(tc)
        clean.append(row)
    return clean


def chunked(lst: list, size: int):
    for i in range(0, len(lst), size):
        yield lst[i : i + size]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ingest question_bank_normalized.json into Supabase."
    )
    parser.add_argument(
        "--file",
        type=Path,
        default=DEFAULT_JSON,
        help=f"Path to the normalized JSON file (default: {DEFAULT_JSON})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be upserted without writing to Supabase.",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=100,
        help="Number of rows per upsert batch (default: 100).",
    )
    args = parser.parse_args()

    # Load + sanitize
    questions = load_questions(args.file)
    questions = sanitize(questions)
    total = len(questions)
    print(f"Loaded {total} questions from {args.file}")

    # Quick summary
    from collections import Counter
    topic_counts  = Counter(q.get("topic")  for q in questions)
    source_counts = Counter(q.get("source") for q in questions)
    form_counts   = Counter(q.get("test_form") for q in questions)
    print("\nBy topic:")
    for t, n in sorted(topic_counts.items()):
        print(f"  {t or 'UNCLASSIFIED':30s}  {n:4d}")
    print("\nBy source:")
    for s, n in sorted(source_counts.items()):
        print(f"  {s or 'unknown':10s}  {n:4d}")
    print("\nBy test_form:")
    for f, n in sorted(form_counts.items()):
        print(f"  {f or 'NONE':15s}  {n:4d}")

    if args.dry_run:
        print(f"\n[DRY RUN] Would upsert {total} rows into {TABLE_NAME}. No writes performed.")
        print(f"Sample row:\n  {json.dumps(questions[0], indent=2)[:500]}...")
        return

    # Connect
    client = get_service_client()

    # Batch upsert
    inserted = 0
    errors   = 0
    batches  = list(chunked(questions, args.chunk_size))
    print(f"\nUploading {total} rows in {len(batches)} batches of {args.chunk_size}…")

    # Try importing tqdm for a progress bar; gracefully degrade
    try:
        from tqdm import tqdm
        batch_iter = tqdm(batches, unit="batch")
    except ImportError:
        batch_iter = batches

    for i, batch in enumerate(batch_iter, 1):
        try:
            response = (
                client.table(TABLE_NAME)
                .upsert(batch, on_conflict="id")
                .execute()
            )
            inserted += len(batch)
        except Exception as exc:
            errors += len(batch)
            print(f"  [ERROR] Batch {i}: {exc}")

    print(f"\n{'='*50}")
    print(f"Done.  Inserted/updated: {inserted}  Errors: {errors}")
    if errors:
        print("WARNING: Some batches failed. Check error messages above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
