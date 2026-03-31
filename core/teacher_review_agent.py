from typing import Any, Dict

from core.logging_utils import get_logger, trace_event, Timer


class TeacherReviewAgent:
    """
    Human-in-the-loop validation using CLI input.

    - Prints learning content + quiz
    - Teacher types: approve | reject
    - On approved, flow continues; on rejected, flow halts
    """

    def __init__(self):
        self.logger = get_logger("teacher_review", "validation.log")

    def review(self, crew_output: Dict[str, Any], student_state: Dict[str, Any]) -> Dict[str, Any]:
        timer = Timer()
        choice = input("Approve this content? Type 'approve' or 'reject': ").strip().lower()
        status = "approved" if choice == "approve" else "rejected"

        duration_ms = round(timer.elapsed_ms(), 2)
        self.logger.info(f"status={status} duration_ms={duration_ms}")
        trace_event("teacher_review", {"status": status})
        return {"review_status": status}
