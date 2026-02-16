from core.tutor_agent import TutorAgent
from core.practical_agent import PracticalAgent
from core.teacher_persona_agent import TeacherPersonaAgent


class EducationCrew:
    """
    Education Crew Node (Extensible Orchestrator)
    """

    def __init__(self):

        # Register agents
        self.agents = [
            TutorAgent(),
            PracticalAgent(),
            TeacherPersonaAgent()
        ]
        # CrewAI role definitions (metadata only)
        self.crew_roles = [
                        {"role": "Tutor", "goal": "Generate learning paths"},
                        {"role": "Practical", "goal": "Generate quizzes"},
                        {"role": "Teacher Persona", "goal": "Define teaching style"}
]


    def run(self, state: dict):
        decision_output = state["decision"]
        student_state = state["student_state"]



        result = {
            "learning_path": [],
            "quiz": [],
            "teacher_style": ""
        }

        # Iterate through agents
        for agent in self.agents:

            # Tutor Agent
            if hasattr(agent, "generate_learning_path"):
                result["learning_path"] = agent.generate_learning_path(
                    decision_output,
                    student_state
                )

            # Practical Agent
            if hasattr(agent, "generate_quiz"):
                result["quiz"] = agent.generate_quiz(
                    decision_output,
                    student_state
                )

            # Teacher Persona Agent
            if hasattr(agent, "apply_persona"):
                result["teacher_style"] = agent.apply_persona(
                    student_state
                )
        state["crew_output"] = result
        return state
