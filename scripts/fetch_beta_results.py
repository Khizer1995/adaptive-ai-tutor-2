"""
scripts/fetch_beta_results.py
==============================
Fetch all beta testing data from Supabase and generate a metrics report.

Usage:
    python scripts/fetch_beta_results.py
"""

import os
import json
from datetime import datetime
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

def main():
    # Connect to Supabase
    url = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
    key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY", "")
    
    if not url or not key:
        print("❌ Error: SUPABASE_URL and SUPABASE_KEY must be set in .env")
        return
    
    supabase = create_client(url, key)
    
    print("=" * 80)
    print("BETA TESTING RESULTS - Cognitive Adaptive AI Tutor")
    print("=" * 80)
    print()
    
    # Fetch user profiles
    print("📊 Fetching user profiles...")
    profiles_response = supabase.table("user_profiles").select("*").execute()
    profiles = profiles_response.data
    
    print(f"✅ Found {len(profiles)} users\n")
    
    # Fetch learning history
    print("📚 Fetching learning history...")
    history_response = supabase.table("learning_history").select("*").execute()
    history = history_response.data
    
    print(f"✅ Found {len(history)} quiz attempts\n")
    
    # Fetch knowledge states
    print("🧠 Fetching knowledge states...")
    try:
        knowledge_response = supabase.table("knowledge_state").select("*").execute()
        knowledge = knowledge_response.data
        print(f"✅ Found {len(knowledge)} knowledge state snapshots\n")
    except Exception as e:
        print(f"⚠️  Could not fetch knowledge_state table: {e}")
        knowledge = []
        print()
    
    print("=" * 80)
    print("USER SUMMARY")
    print("=" * 80)
    
    for i, profile in enumerate(profiles, 1):
        print(f"\n{i}. {profile.get('full_name', 'Unknown')} ({profile.get('student_id', 'N/A')})")
        print(f"   Email: {profile.get('email', 'N/A')}")
        print(f"   Level: {profile.get('level', 'N/A')}")
        print(f"   Learning Style: {profile.get('learning_style', 'N/A')}")
        print(f"   Current Topic: {profile.get('current_topic', 'N/A')}")
        print(f"   Current Subtopic: {profile.get('current_subtopic', 'N/A')}")
        print(f"   Last Score: {profile.get('last_score', 0):.2%}")
        print(f"   Learning Gain: {profile.get('learning_gain', 0):.2%}")
        print(f"   Pretest Score: {profile.get('pretest_score') or 'N/A'}")
        print(f"   Posttest Score: {profile.get('posttest_score') or 'N/A'}")
        print(f"   Engagement: {profile.get('engagement', 'N/A')}")
        print(f"   Last Active: {profile.get('last_active', 'N/A')}")
        
        # Find user's quiz attempts
        user_history = [h for h in history if h.get('student_id') == profile.get('student_id')]
        if user_history:
            print(f"\n   📝 Quiz Attempts ({len(user_history)}):")
            for h in user_history:
                passed_icon = "✅" if h.get('passed') else "❌"
                print(f"      {passed_icon} {h.get('topic', 'N/A')} / {h.get('subtopic', 'N/A')}")
                print(f"         Score: {h.get('score', 0):.2%} ({h.get('question_count', 0)} questions)")
                print(f"         Type: {h.get('record_type', 'quiz')}")
                print(f"         Date: {h.get('recorded_at', 'N/A')}")
        else:
            print(f"\n   📝 No quiz attempts yet")
    
    # Overall metrics
    print("\n" + "=" * 80)
    print("OVERALL METRICS")
    print("=" * 80)
    
    if history:
        total_attempts = len(history)
        passed_attempts = len([h for h in history if h.get('passed')])
        pass_rate = (passed_attempts / total_attempts * 100) if total_attempts > 0 else 0
        
        avg_score = sum(h.get('score', 0) for h in history) / total_attempts if total_attempts > 0 else 0
        
        print(f"\nTotal Quiz Attempts: {total_attempts}")
        print(f"Passed Attempts: {passed_attempts}")
        print(f"Pass Rate: {pass_rate:.1f}%")
        print(f"Average Score: {avg_score:.2%}")
        
        # Topics covered
        topics = set(h.get('topic') for h in history if h.get('topic'))
        print(f"\nTopics Covered: {len(topics)}")
        for topic in sorted(topics):
            topic_attempts = [h for h in history if h.get('topic') == topic]
            topic_avg = sum(h.get('score', 0) for h in topic_attempts) / len(topic_attempts)
            print(f"  - {topic}: {len(topic_attempts)} attempts, avg {topic_avg:.2%}")
    else:
        print("\n⚠️  No quiz attempts recorded yet")
    
    if profiles:
        avg_learning_gain = sum(p.get('learning_gain', 0) for p in profiles) / len(profiles)
        users_with_pretest = len([p for p in profiles if p.get('pretest_score') is not None])
        users_with_posttest = len([p for p in profiles if p.get('posttest_score') is not None])
        
        print(f"\nAverage Learning Gain: {avg_learning_gain:.2%}")
        print(f"Users with Pretest: {users_with_pretest}")
        print(f"Users with Posttest: {users_with_posttest}")
    
    # Save to JSON
    output_file = "data/beta_testing_report.json"
    report = {
        "generated_at": datetime.now().isoformat(),
        "total_users": len(profiles),
        "total_quiz_attempts": len(history),
        "profiles": profiles,
        "learning_history": history,
        "knowledge_states": knowledge,
    }
    
    os.makedirs("data", exist_ok=True)
    with open(output_file, "w") as f:
        json.dump(report, f, indent=2, default=str)
    
    print(f"\n📄 Full report saved to: {output_file}")
    print("\n" + "=" * 80)

if __name__ == "__main__":
    main()
