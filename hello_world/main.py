from hello_world.models import StudentProfile
from hello_world.profile_manager import ProfileManager


# 1. Setup the manager
manager = ProfileManager()

# 2. Create a profile (Day 2 work)
kishore = StudentProfile(student_id="KISH-001", name="Kishore")

# 3. Simulate a change (e.g., student finished a topic)
kishore.completed_topics.append("Introduction to LLMs")
kishore.knowledge_level = "intermediate"

# 4. SAVE (Day 3 Task)
manager.save_profile(kishore)

# 5. LOAD (Day 3 Task)
reloaded_kishore = manager.load_profile("KISH-001")
print(f"✅ Reloaded {reloaded_kishore.name}'s level: {reloaded_kishore.knowledge_level}")
print(f"✅ Completed Topics: {reloaded_kishore.completed_topics}")