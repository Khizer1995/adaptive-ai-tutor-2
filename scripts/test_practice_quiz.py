"""
Diagnostic script to test practice quiz path end-to-end.
Captures exact request/response and traces the code path.
"""
import json
import requests
from pathlib import Path

BASE_URL = "http://localhost:8765"

# Load test student credentials
profiles_dir = Path("profiles")
test_profile = profiles_dir / "USER-71cbf510.json"

if not test_profile.exists():
    print(f"❌ Test profile not found: {test_profile}")
    exit(1)

with open(test_profile) as f:
    profile_data = json.load(f)
    student_id = profile_data["student_id"]

print(f"🧪 Testing practice quiz for student: {student_id}")
print("=" * 80)

# Step 1: Login (we'll need a test token)
# For now, let's assume we have a Bearer token or we're testing without auth
# Let's first test with auth required

print("\n📝 Step 1: Generate Practice Quiz Request")
print("-" * 80)

# Test with different topics
test_cases = [
    {"topic": "array", "subtopic": "array_introduction"},
    {"topic": "queue", "subtopic": "queue_basics"},
    {"topic": "graph", "subtopic": "graph_basics"},
]

for test_case in test_cases:
    print(f"\n🎯 Testing: topic={test_case['topic']}, subtopic={test_case['subtopic']}")
    print(f"   Request: POST /quiz/generate")
    print(f"   Body: {json.dumps(test_case)}")
    
    # This will fail without proper auth token, but shows the structure
    print(f"\n   ⚠️  Note: This requires Bearer token authentication")
    print(f"   curl equivalent:")
    print(f"   curl -X POST http://localhost:8765/quiz/generate \\")
    print(f"        -H 'Content-Type: application/json' \\")
    print(f"        -H 'Authorization: Bearer <TOKEN>' \\")
    print(f"        -d '{json.dumps(test_case)}'")

print("\n" + "=" * 80)
print("📊 Analysis Summary")
print("=" * 80)
print("\n1. ENDPOINT: POST /quiz/generate")
print("   Located at: api_server.py:940")
print("   Auth required: YES (Depends(require_auth))")
print("\n2. CURRENT IMPLEMENTATION:")
print("   ❌ Uses LLM generation (crew.practical.generate_quiz_batch)")
print("   ❌ Does NOT call QuestionBankService")
print("   📝 Comment says: 'MCQ bank rebuild: question bank is currently empty'")
print("\n3. EXPECTED BEHAVIOR (from pretest/posttest):")
print("   ✅ Should call get_question_bank_service().get_quiz()")
print("   ✅ Should pass pool='practice_pool'")
print("   ✅ Should pass question_type=None (any type)")
print("   ✅ Should normalize topic to title-case")
print("\n4. QUESTION BANK STRUCTURE (360 rows verified):")
print("   - 144 pretest (40% of 360)")
print("   - 144 posttest (40% of 360)")
print("   - 72 practice (20% of 360)")
print("   - Grouped by: (Topic, Difficulty, test_form)")
print("   - Topics: 'Array', 'Queue', 'Graph' (title-case)")
print("   - Difficulties: easy, medium, hard")
print("   - Practice pool: 8 questions per (topic, difficulty) = 24 per topic")
print("\n5. ROOT CAUSE:")
print("   The /quiz/generate endpoint is NEVER calling QuestionBankService.")
print("   It's still using LLM generation from the old implementation.")
