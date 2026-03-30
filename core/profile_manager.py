"""
Profile Manager  —  Kishore's Work
Handles reading and writing student profiles to/from JSON files.
Each profile is stored at: profiles/<student_id>.json
"""

from typing import List, Dict, Any, Optional, cast
from datetime import datetime, timezone
import json
import os
from core.student_profile_schema import StudentProfile


class ProfileManager:
    """
    Manages persistent student profiles stored as JSON files.

    Usage
    -----
    pm = ProfileManager()

    # Load existing profile as dict (compatible with all agents)
    state = pm.load("KISH-001")

    # Save updated state back
    pm.save("KISH-001", state)

    # Create a brand-new profile
    pm.create_profile("SHAZ-002", name="Shazi", level="beginner")
    """

    PROFILES_DIR = "profiles"

    def __init__(self, profiles_dir: str = None):
        self.profiles_dir = profiles_dir or self.PROFILES_DIR
        os.makedirs(self.profiles_dir, exist_ok=True)

    def _path(self, student_id: str) -> str:
        return os.path.join(self.profiles_dir, f"{student_id}.json")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load(self, student_id: str) -> dict:
        """
        Load a student profile by ID.
        Returns a plain dict suitable for use with all agents.
        Raises FileNotFoundError if profile doesn't exist.
        """
        path = self._path(student_id)
        if not os.path.exists(path):
            raise FileNotFoundError(
                f"Profile '{student_id}' not found at {path}. "
                f"Use create_profile() to initialise one."
            )
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)

        # Normalise via schema so field names are consistent
        profile = StudentProfile.from_dict(raw)
        return cast(Dict[str, Any], profile.to_dict())

    def save(self, student_id: str, state: dict) -> None:
        """
        Persist updated student state back to JSON.
        Automatically stamps last_active timestamp.
        """
        state["last_active"] = datetime.now(timezone.utc).isoformat()
        # Normalise keys for consistency
        state.setdefault("student_id", student_id)
        path = self._path(student_id)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=4)
        print(f"[ProfileManager] Saved profile → {path}")

    def create_profile(
        self,
        student_id: str,
        name: str,
        level: str = "beginner",
        learning_style: str = "balanced",
    ) -> dict:
        """
        Create and persist a new student profile.
        Returns the profile dict.
        """
        profile = StudentProfile(
            student_id=student_id,
            name=name,
            level=level,
            learning_style=learning_style,
            last_active=datetime.now(timezone.utc).isoformat(),
            accuracy_history=[],
            learning_gain_history=[],
        )
        data = profile.to_dict()
        path = self._path(student_id)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
        print(f"[ProfileManager] Created new profile → {path}")
        return data

    def list_profiles(self) -> List[str]:
        """Return a list of all student IDs that have saved profiles."""
        return [
            f.replace(".json", "")
            for f in os.listdir(self.profiles_dir)
            if f.endswith(".json")
        ]


# ------------------------------------------------------------------
# Quick self-test
# ------------------------------------------------------------------
if __name__ == "__main__":
    pm = ProfileManager()
    print("Available profiles:", pm.list_profiles())
    for sid in pm.list_profiles():
        try:
            p = pm.load(sid)
            print(f"  {sid}: level={p['level']}, topic={p['current_topic']}")
        except Exception as e:
            print(f"  {sid}: ERROR — {e}")
