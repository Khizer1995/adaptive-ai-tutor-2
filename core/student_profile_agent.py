from typing import Dict, Any

from core.logging_utils import get_logger, trace_event, Timer
from core.profile_manager import ProfileManager


class StudentProfileAgent:
    """
    Student Profile Agent (AIA-PAL alignment)

    - Persists student state after each cycle
    - Provides a single place to manage profile updates
    """

    def __init__(self, profiles_dir: str = None):
        self.profile_manager = ProfileManager(profiles_dir=profiles_dir)
        self.logger = get_logger("student_profile", "student_profile.log")

    def persist(self, student_state: Dict[str, Any]) -> Dict[str, Any]:
        timer = Timer()
        student_id = student_state.get("student_id", "UNKNOWN")
        if not student_id or student_id == "UNKNOWN":
            self.logger.warning("student_id missing; skipping profile save.")
            trace_event("student_profile_skipped", {"reason": "missing_student_id"})
            return student_state

        self.profile_manager.save(student_id, student_state)
        duration_ms = round(timer.elapsed_ms(), 2)
        self.logger.info(f"student_id={student_id} saved duration_ms={duration_ms}")
        trace_event(
            "student_profile_saved",
            {"student_id": student_id, "duration_ms": duration_ms},
        )
        return student_state
