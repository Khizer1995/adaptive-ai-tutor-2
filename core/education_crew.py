from core.tutor_agent import TutorAgent
from core.practical_agent import PracticalAgent
from core.teacher_persona_agent import TeacherPersonaAgent


class EducationCrew:
    """
    Education Crew Node (Extensible Orchestrator)
    """

    def __init__(self):

        self.agents = [
            TutorAgent(),
            PracticalAgent(),
            TeacherPersonaAgent()
        ]

        self.crew_roles = [
            {"role": "Tutor", "goal": "Generate learning paths"},
            {"role": "Practical", "goal": "Generate quizzes"},
            {"role": "Teacher Persona", "goal": "Define teaching style"}
        ]

    # 🔥 NEW STANDARD INTERFACE
    def execute(self, decision_output: dict, student_state: dict):
        """
        Standard interface used by tests and simulation.
        """
        state = {
            "decision": decision_output,
            "student_state": student_state
        }

        state = self.run(state)
        return state["crew_output"]

    # Internal orchestration method
    def run(self, state: dict):

        decision_output = state["decision"]
        student_state = state["student_state"]

        result = {
            "learning_path": [],
            "quiz": [],
            "teacher_style": ""
        }

        for agent in self.agents:

            if hasattr(agent, "generate_learning_path"):
                result["learning_path"] = agent.generate_learning_path(
                    decision_output,
                    student_state
                )

            if hasattr(agent, "generate_quiz"):
                result["quiz"] = agent.generate_quiz(
                    decision_output,
                    student_state
                )

            if hasattr(agent, "apply_persona"):
                result["teacher_style"] = agent.apply_persona(
                    student_state
                )

        state["crew_output"] = result
        return state
