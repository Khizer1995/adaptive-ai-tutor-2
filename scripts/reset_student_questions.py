#!/usr/bin/env python3
"""
Reset asked_questions for a student to allow re-taking quizzes.

Usage:
    python scripts/reset_student_questions.py <student_id>
    python scripts/reset_student_questions.py USER-71cbf510

This is a demo-reset tool for testing. In production, students would not
be able to reset their question history.

The script:
1. Counts existing asked_questions rows for the student
2. Deletes all rows for that student_id
3. Reports the count before/after
"""

import sys
import os
from pathlib import Path

# Add parent directory to path so we can import core modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.supabase_client import get_supabase


def reset_student_questions(student_id: str) -> None:
    """Delete all asked_questions rows for a given student_id."""
    
    print(f"🔄 Resetting asked_questions for student: {student_id}")
    print("=" * 80)
    
    try:
        sb = get_supabase()
        
        # Count before
        count_before_resp = (
            sb.table("asked_questions")
            .select("*", count="exact")
            .eq("student_id", student_id)
            .execute()
        )
        count_before = count_before_resp.count or 0
        
        print(f"\n📊 Before: {count_before} asked_questions rows")
        
        if count_before == 0:
            print(f"✅ Student {student_id} has no asked_questions history.")
            return
        
        # Show breakdown by context
        rows_before = count_before_resp.data or []
        contexts = {}
        for row in rows_before:
            ctx = row.get("context", "unknown")
            contexts[ctx] = contexts.get(ctx, 0) + 1
        
        print("\n   Breakdown by context:")
        for ctx, count in sorted(contexts.items()):
            print(f"   - {ctx}: {count} questions")
        
        # Confirm deletion
        print(f"\n⚠️  This will DELETE all {count_before} asked_questions rows for {student_id}")
        confirm = input("   Type 'yes' to confirm: ").strip().lower()
        
        if confirm != "yes":
            print("❌ Aborted. No changes made.")
            return
        
        # Delete
        print(f"\n🗑️  Deleting...")
        delete_resp = (
            sb.table("asked_questions")
            .delete()
            .eq("student_id", student_id)
            .execute()
        )
        
        # Count after
        count_after_resp = (
            sb.table("asked_questions")
            .select("*", count="exact")
            .eq("student_id", student_id)
            .execute()
        )
        count_after = count_after_resp.count or 0
        
        print(f"\n📊 After: {count_after} asked_questions rows")
        print(f"✅ Deleted: {count_before - count_after} rows")
        
        if count_after > 0:
            print(f"⚠️  Warning: {count_after} rows still remain!")
        else:
            print(f"\n🎉 Success! Student {student_id} can now see all questions again.")
            print("   Next practice/pretest/posttest quiz will fetch from full pool.")
        
    except Exception as exc:
        print(f"\n❌ Error: {exc}")
        sys.exit(1)


def main():
    if len(sys.argv) != 2:
        print("Usage: python scripts/reset_student_questions.py <student_id>")
        print("\nExample:")
        print("  python scripts/reset_student_questions.py USER-71cbf510")
        sys.exit(1)
    
    student_id = sys.argv[1].strip()
    
    if not student_id:
        print("❌ Error: student_id cannot be empty")
        sys.exit(1)
    
    reset_student_questions(student_id)


if __name__ == "__main__":
    main()
