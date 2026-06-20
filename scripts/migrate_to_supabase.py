"""
scripts/migrate_to_supabase.py
==============================
Migrate existing JSON profile data to Supabase.

Usage:
    # Dry run (shows what would be inserted, no writes)
    python scripts/migrate_to_supabase.py --dry-run

    # Real migration
    python scripts/migrate_to_supabase.py

NOTE: This script migrates legacy profiles (KISH-001, SHAZ-001, etc.)
into Supabase as reference data. These profiles are NOT linked to any
auth.users row (since they predate authentication). They are stored in
the knowledge_states and learning_history tables using their original
student_id as key, with user_id = NULL workaround via service_role if
available, or skipped if only anon key is available.

For new authenticated users, profile creation happens automatically at
signup via the /auth/signup endpoint.
"""

import json
import os
import sys
import argparse
from pathlib import Path
from datetime import datetime, timezone

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

PROFILES_DIR = Path(__file__).parent.parent / "profiles"
SURVEY_RESPONSES_PATH = Path(__file__).parent.parent / "data" / "survey_responses.jsonl"


def load_all_profiles() -> list[dict]:
    """Load all JSON profiles from the profiles/ directory."""
    profiles = []
    for json_file in PROFILES_DIR.glob("*.json"):
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            data["_source_file"] = json_file.name
            profiles.append(data)
            print(f"  Loaded: {json_file.name}")
        except Exception as e:
            print(f"  ERROR loading {json_file.name}: {e}")
    return profiles


def load_survey_responses() -> list[dict]:
    """Load all survey responses from JSONL file."""
    if not SURVEY_RESPONSES_PATH.exists():
        return []
    records = []
    with open(SURVEY_RESPONSES_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return records


def analyze_profiles(profiles: list[dict]) -> None:
    """Print analysis of JSON data to be migrated."""
    print("\n" + "="*60)
    print("JSON DATA ANALYSIS")
    print("="*60)

    total_history = 0
    for profile in profiles:
        sid = profile.get("student_id", "unknown")
        level = profile.get("level", "?")
        topic = profile.get("current_topic", "none")
        history = profile.get("learning_history", [])
        total_history += len(history)
        concepts = profile.get("knowledge_state", {}).get("concepts", {})
        print(f"\n  Profile: {sid}")
        print(f"    Level: {level} | Topic: {topic}")
        print(f"    Learning history entries: {len(history)}")
        print(f"    Concepts tracked: {list(concepts.keys())}")
        print(f"    Last score: {profile.get('last_score', 0)}")

    print(f"\n  Total profiles: {len(profiles)}")
    print(f"  Total history entries: {total_history}")

    survey_records = load_survey_responses()
    print(f"  Survey responses (JSONL): {len(survey_records)}")
    print("="*60)


def migrate_with_service_role(profiles: list[dict], dry_run: bool = False) -> None:
    """
    Attempt to migrate using Supabase service_role key.
    Since RLS requires auth.uid() for inserts, legacy profiles need service_role
    or a special bypass. This version stores them in a legacy_profiles JSON dump.
    """
    print("\n" + "="*60)
    print("MIGRATION PLAN")
    print("="*60)

    # For legacy profiles that don't have a real auth.uid(), we export them
    # as a JSON summary so they can be loaded manually or referenced.
    output_path = Path(__file__).parent.parent / "data" / "legacy_profiles_export.json"

    export_data = {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "note": (
            "These are pre-authentication profiles. To link them to real Supabase users, "
            "have the student sign up and use their new USER-xxxx student_id. "
            "Their new authenticated profile will be created fresh on first login."
        ),
        "profiles": []
    }

    for profile in profiles:
        sid = profile.get("student_id", "UNKNOWN")
        learning_history = profile.get("learning_history", [])
        knowledge_state = profile.get("knowledge_state", {})

        profile_summary = {
            "student_id": sid,
            "name": profile.get("name", "Student"),
            "level": profile.get("level", "beginner"),
            "subject": profile.get("subject", "dsa"),
            "current_topic": profile.get("current_topic"),
            "last_score": profile.get("last_score", 0.0),
            "learning_history_count": len(learning_history),
            "learning_history": learning_history,
            "knowledge_state": knowledge_state,
            "progress": profile.get("progress", []),
            "knowledge_events": profile.get("knowledge_events", []),
            "pretest_score": profile.get("pretest_score"),
            "posttest_score": profile.get("posttest_score"),
            "learning_gain": profile.get("learning_gain", 0.0),
        }
        export_data["profiles"].append(profile_summary)

        print(f"\n  [{'DRY RUN' if dry_run else 'EXPORT'}] Profile: {sid}")
        print(f"    → learning_history: {len(learning_history)} entries")
        print(f"    → knowledge_state concepts: {list(knowledge_state.get('concepts', {}).keys())}")

    if not dry_run:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(export_data, f, indent=2)
        print(f"\n  ✅ Exported to: {output_path}")
        print("  ℹ️  New authenticated users will get fresh profiles automatically.")
        print("  ℹ️  To migrate a legacy user: have them sign up, then the backend")
        print("      will create USER-xxxx profile. You can manually copy data from")
        print("      the exported JSON above if needed.")
    else:
        print("\n  [DRY RUN] — no files written.")

    # Survey responses export
    survey_records = load_survey_responses()
    if survey_records:
        survey_export_path = Path(__file__).parent.parent / "data" / "legacy_surveys_export.json"
        print(f"\n  Survey responses: {len(survey_records)} entries")
        if not dry_run:
            with open(survey_export_path, "w", encoding="utf-8") as f:
                json.dump({"records": survey_records}, f, indent=2)
            print(f"  ✅ Survey export: {survey_export_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Migrate JSON profiles to Supabase export format"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Analyze and plan migration without writing anything",
    )
    args = parser.parse_args()

    print("\n🚀 Cognitive Adaptive AI Tutor — Profile Migration Tool")
    print(f"   Mode: {'DRY RUN' if args.dry_run else 'LIVE'}")

    print("\nLoading JSON profiles...")
    profiles = load_all_profiles()

    if not profiles:
        print("  No profiles found in profiles/ directory.")
        return

    analyze_profiles(profiles)
    migrate_with_service_role(profiles, dry_run=args.dry_run)

    print("\n✅ Migration complete!")
    print("\nNext Steps:")
    print("  1. Run the SQL schema: scripts/supabase_schema.sql in Supabase SQL Editor")
    print("  2. New users sign up via the UI → profiles created automatically")
    print("  3. Legacy data in data/legacy_profiles_export.json for reference")


if __name__ == "__main__":
    main()
