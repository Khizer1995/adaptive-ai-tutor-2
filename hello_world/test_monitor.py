from crew_setup import run_monitoring_check
from profile_manager import ProfileManager

# Test input representing a confused student
frustrated_chat = "Student: I am so confused! This math problem is way too hard and I don't understand."

print("--- Starting Gemini-Powered Monitor Test ---")

# Execute the CrewAI logic
result = run_monitoring_check(frustrated_chat)

# Verify the update in your local JSON database
manager = ProfileManager()
profile = manager.load_profile("KISH-001")

print(f"\nAnalysis Result: {result}")
print(f"Updated Frustration Level: {profile.frustration_level}")