from models import StudentProfile
from pydantic import ValidationError

# 1. Create a valid profile for a new student
try:
    kishore_profile = StudentProfile(
        student_id="KISH-001",
        name="Kishore",
        knowledge_level="intermediate",
        interests=["Big Data", "Python"]
    )
    print(f"✅ Success! Profile created for: {kishore_profile.name}")
    print(f"Current Level: {kishore_profile.knowledge_level}")
except ValidationError as e:
    print(f"❌ Creation failed: {e}")

# 2. Test the "Guardrails" (Invalid Data)
print("\nTesting validation guardrails...")
try:
    # This should fail because frustration_level must be <= 10
    kishore_profile.frustration_level = 99 
except ValidationError:
    print("✅ Guardrail caught it! Frustration level cannot be 99.")