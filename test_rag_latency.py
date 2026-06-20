"""
Quick test to verify RAG latency is being captured correctly.
Run this after the fix to confirm it works.
"""

from core.tutor_agent import TutorAgent
from core.education_crew import EducationCrew
from core.profile_manager import ProfileManager
import json

print("=" * 60)
print("Testing RAG Latency Capture")
print("=" * 60)

# Test 1: Direct TutorAgent test
print("\n[Test 1] TutorAgent.generate_learning_path()")
print("-" * 60)

ta = TutorAgent()
decision = {"action": "increase_support"}
student_state = {
    "student_id": "TEST",
    "level": "beginner",
    "current_topic": "array",
    "subject": "dsa",
    "learning_style": "balanced",
    "last_score": 0.5,
    "engagement": "medium"
}

try:
    result = ta.generate_learning_path(decision, student_state)
    rag_latency = result.get("rag_latency_ms", "MISSING")
    
    if rag_latency == "MISSING":
        print("❌ FAILED: rag_latency_ms not in result")
    elif rag_latency == 0.0:
        print("⚠️  WARNING: rag_latency_ms is 0.0 (may be okay if no retrieval)")
    else:
        print(f"✅ SUCCESS: rag_latency_ms = {rag_latency}ms")
        
    print(f"\nResult keys: {list(result.keys())}")
    print(f"RAG chunks retrieved: {len(result.get('rag_chunks', []))}")
    
except Exception as e:
    print(f"❌ ERROR: {e}")

# Test 2: EducationCrew test
print("\n[Test 2] EducationCrew._extract_learning()")
print("-" * 60)

crew = EducationCrew()

# Mock learning path result
mock_learning_result = {
    "llm_synthesis": "Test content",
    "rag_chunks": ["chunk1", "chunk2"],
    "rag_chunk_records": [],
    "engineered_query": "test query",
    "adaptive_ctx": {},
    "rag_latency_ms": 123.45  # Mock value
}

try:
    extracted = crew._extract_learning(mock_learning_result)
    rag_latency = extracted.get("rag_latency_ms", "MISSING")
    
    if rag_latency == "MISSING":
        print("❌ FAILED: rag_latency_ms not extracted")
    elif rag_latency != 123.45:
        print(f"❌ FAILED: Expected 123.45, got {rag_latency}")
    else:
        print(f"✅ SUCCESS: rag_latency_ms = {rag_latency}ms (correctly extracted)")
        
except Exception as e:
    print(f"❌ ERROR: {e}")

# Test 3: Check metrics log
print("\n[Test 3] Check Recent Metrics Log")
print("-" * 60)

try:
    with open("logs/metrics_log.jsonl", "r") as f:
        lines = f.readlines()
    
    if not lines:
        print("⚠️  No metrics logged yet")
    else:
        # Check last 3 entries
        print(f"Found {len(lines)} metric entries. Checking last 3:")
        
        for i, line in enumerate(lines[-3:], 1):
            try:
                metric = json.loads(line)
                rag_lat = metric.get("rag_latency_ms", "MISSING")
                
                if rag_lat == "MISSING":
                    print(f"  {i}. ❌ No rag_latency_ms field")
                elif rag_lat == 0.0:
                    print(f"  {i}. ⚠️  rag_latency_ms = 0.0")
                else:
                    print(f"  {i}. ✅ rag_latency_ms = {rag_lat}ms")
            except json.JSONDecodeError:
                print(f"  {i}. ❌ Invalid JSON")
                
except FileNotFoundError:
    print("⚠️  metrics_log.jsonl not found yet")
except Exception as e:
    print(f"❌ ERROR: {e}")

# Test 4: Check student state
print("\n[Test 4] Check Student State for RAG Timing")
print("-" * 60)

try:
    pm = ProfileManager()
    profiles = pm.list_profiles()
    
    if not profiles:
        print("⚠️  No profiles found")
    else:
        profile_id = profiles[0]
        state = pm.load(profile_id)
        rag_timing = state.get("_rag_latency_ms", "MISSING")
        
        print(f"Profile: {profile_id}")
        if rag_timing == "MISSING":
            print("⚠️  No _rag_latency_ms in profile (will be set on next run)")
        elif rag_timing == 0.0:
            print("⚠️  _rag_latency_ms = 0.0")
        else:
            print(f"✅ _rag_latency_ms = {rag_timing}ms")
            
except Exception as e:
    print(f"❌ ERROR: {e}")

# Summary
print("\n" + "=" * 60)
print("SUMMARY")
print("=" * 60)
print("""
If all tests show ✅ or ⚠️ (warning), the fix is working!

Next steps:
1. Run system: python run_langgraph.py
2. Check this test again
3. Generate report: python scripts/generate_eval_report.py
4. Verify RAG latency > 0 in report

Note: ⚠️ warnings are okay if:
- System hasn't run yet (no metrics logged)
- Profile hasn't been updated yet
- Retrieval legitimately took 0ms (cached or no results)
""")
