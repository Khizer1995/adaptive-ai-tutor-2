import os
from models import StudentProfile

class ProfileManager:
    def __init__(self, storage_dir="profiles"):
        self.storage_dir = storage_dir
        # Create the profiles directory if it doesn't exist
        if not os.path.exists(self.storage_dir):
            os.makedirs(self.storage_dir)

    def get_file_path(self, student_id: str):
        return os.path.join(self.storage_dir, f"{student_id}.json")

    def save_profile(self, profile: StudentProfile):
        """Saves a StudentProfile object to a JSON file."""
        file_path = self.get_file_path(profile.student_id)
        with open(file_path, "w") as f:
            # Pydantic's built-in way to turn a model into a JSON string
            f.write(profile.model_dump_json(indent=4))
        print(f"📁 Profile saved to {file_path}")

    def load_profile(self, student_id: str) -> StudentProfile:
        """Loads a JSON file and returns a StudentProfile object."""
        file_path = self.get_file_path(student_id)
        if not os.path.exists(file_path):
            print(f"⚠️ No profile found for {student_id}. Creating a new one.")
            return None
        
        with open(file_path, "r") as f:
            json_data = f.read()
            # Pydantic's built-in way to turn JSON back into a Python object
            return StudentProfile.model_validate_json(json_data)