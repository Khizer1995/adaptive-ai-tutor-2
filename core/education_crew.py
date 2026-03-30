from core.tutor_agent import TutorAgent
from core.practical_agent import PracticalAgent
from core.teacher_persona_agent import TeacherPersonaAgent
from core.logging_utils import get_logger, trace_event, Timer


class EducationCrew:
    """
    Adaptive Education Crew (Upgraded)

    Dynamically orchestrates agents based on decision output.
    """

    def __init__(self):
        self.tutor = TutorAgent()
        self.practical = PracticalAgent()
        self.persona = TeacherPersonaAgent()
        self.logger = get_logger("education_crew", "crew.log")

    def execute(self, decision_output: dict, student_state: dict):
        state = {
            "decision": decision_output,
            "student_state": student_state
        }

        state = self.run(state)
        return state["crew_output"]

    def run(self, state: dict):
        timer = Timer()

        decision = state["decision"]
        student_state = state["student_state"]
        action = decision.get("action", "default")

        result = {
            "learning_path": None,
            "quiz": [],
            "teacher_style": "",
            "rag_chunks": [],
            "engineered_query": "",
            "decision": decision,
        }

        # -----------------------------------
        # 1. Always apply teaching persona
        # -----------------------------------
        if hasattr(self.persona, "apply_persona"):
            result["teacher_style"] = self.persona.apply_persona(student_state)

        # -----------------------------------
        # 2. Action-based orchestration
        # -----------------------------------

        # 🔹 Increase support → detailed explanation + simple quiz
        if action in ["increase_support", "reinforce_basics"]:
            lp = self.tutor.generate_learning_path(decision, student_state)
            result.update(self._extract_learning(lp))

            result["quiz"] = self.practical.generate_quiz(decision, student_state)

        # 🔹 Adjust quiz → focus on practice
        elif action == "adjust_quiz":
                # Keep learning + quiz (better demo)
            lp = self.tutor.generate_learning_path(decision, student_state)
            result.update(self._extract_learning(lp))

            result["quiz"] = self.practical.generate_quiz(decision, student_state)

        # 🔹 Increase challenge → advanced content + harder quiz
        elif action in ["increase_challenge", "challenge_with_variation"]:
            lp = self.tutor.generate_learning_path(decision, student_state)
            result.update(self._extract_learning(lp))

            result["quiz"] = self.practical.generate_quiz(decision, student_state)

        # 🔹 Advance topic → new learning path only
        elif action == "advance_topic":
            # Move to next topic (handled by TutorAgent)
            student_state["current_topic"] = None

            lp = self.tutor.generate_learning_path(decision, student_state)
            result.update(self._extract_learning(lp))

        # 🔹 Default fallback
        else:
            lp = self.tutor.generate_learning_path(decision, student_state)
            result.update(self._extract_learning(lp))

        state["crew_output"] = result
        duration_ms = round(timer.elapsed_ms(), 2)
        self.logger.info(
            f"action={action} topic='{student_state.get('current_topic')}' "
            f"quiz_len={len(result.get('quiz', []))} duration_ms={duration_ms}"
        )
        trace_event(
            "crew_completed",
            {
                "action": action,
                "topic": student_state.get("current_topic"),
                "quiz_len": len(result.get("quiz", [])),
                "duration_ms": duration_ms,
            },
        )
        return state

    # -----------------------------------
    # Helper function (clean extraction)
    # -----------------------------------
    def _extract_learning(self, learning_path_result):

        if isinstance(learning_path_result, dict):
            return {
                "learning_path": learning_path_result.get("llm_synthesis"),
                "rag_chunks": learning_path_result.get("rag_chunks", []),
                "engineered_query": learning_path_result.get("engineered_query", "")
            }

        return {"learning_path": learning_path_result}
