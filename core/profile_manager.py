"""
Profile Manager  —  Kishore's Work
Handles reading and writing student profiles to/from JSON files.
Each profile is stored at: profiles/<student_id>.json
"""

from typing import List, Dict, Any, Optional, cast
from datetime import datetime, timezone
import json
import os
import tempfile
from core.student_profile_schema import StudentProfile
try:
    from core.supabase_sync import sync_student_state as _supabase_sync
except Exception:  # supabase not configured — degrade gracefully
    _supabase_sync = None  # type: ignore[assignment]


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

    def save(self, student_id: str, state: dict, user_id: Optional[str] = None) -> None:
        """
        Persist updated student state back to JSON.
        Automatically stamps last_active timestamp.
        Uses atomic write (temp file + rename) to prevent corruption on crash.

        Parameters
        ----------
        student_id : Profile ID, e.g. "USER-a1b2c3d4".
        state      : Full student state dict.
        user_id    : Supabase Auth UUID. When provided the state is also
                     mirrored to Supabase (user_profiles, learning_state,
                     knowledge_state). Omit for legacy / unauthenticated saves.
        """
        state["last_active"] = datetime.now(timezone.utc).isoformat()
        # Normalise keys for consistency
        state.setdefault("student_id", student_id)
        path = self._path(student_id)
        # Write to a temp file in the same directory then atomically rename
        # so a crash mid-write never leaves a corrupt file.
        dir_name = os.path.dirname(os.path.abspath(path))
        fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=4)
            os.replace(tmp_path, path)
        except Exception:
            # Clean up the temp file if something went wrong
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

        # Mirror to Supabase (best-effort — never raises)
        if _supabase_sync is not None:
            try:
                _supabase_sync(state, user_id=user_id)
            except Exception as exc:  # noqa: BLE001
                import logging
                logging.getLogger(__name__).warning(
                    "Supabase sync skipped for %s: %s", student_id, exc
                )

    def create_profile(
        self,
        student_id: str,
        name: str,
        level: str = "beginner",
        learning_style: str = "balanced",
        user_id: Optional[str] = None,
    ) -> dict:
        """
        Create and persist a new student profile.
        Returns the profile dict.

        Parameters
        ----------
        user_id : When provided the new profile is also written to Supabase.
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

        # Mirror to Supabase on creation (best-effort)
        if _supabase_sync is not None and user_id:
            try:
                _supabase_sync(data, user_id=user_id)
            except Exception as exc:  # noqa: BLE001
                import logging
                logging.getLogger(__name__).warning(
                    "Supabase sync on create_profile skipped for %s: %s", student_id, exc
                )
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
