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

        print("\n" + "=" * 60)
        print("TEACHER REVIEW REQUIRED")
        print("=" * 60)
        print(f"Student   : {student_state.get('student_id')} ({student_state.get('name')})")
        print(f"Level     : {student_state.get('level')}")
        print(f"Topic     : {student_state.get('current_topic')}")
        print(f"Decision  : {crew_output.get('decision', {})}")
        print(f"Persona   : {crew_output.get('teacher_style')}")
        print("\n--- Learning Path ---")
        lp = crew_output.get("learning_path", "")
        if isinstance(lp, str):
            print(lp[:800])
        else:
            print(lp)
        print("\n--- Quiz ---")
        print(crew_output.get("quiz", []))
        print("\nApprove this content? Type 'approve' or 'reject':")

        choice = input("> ").strip().lower()
        status = "approved" if choice == "approve" else "rejected"

        duration_ms = round(timer.elapsed_ms(), 2)
        self.logger.info(f"status={status} duration_ms={duration_ms}")
        trace_event("teacher_review", {"status": status})
        return {"review_status": status}
