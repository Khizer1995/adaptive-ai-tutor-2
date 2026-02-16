from core.decision_engine import DecisionEngine
from core.education_crew import EducationCrew
from core.monitor_agent import MonitorAgent


class AdaptiveLearningSimulation:
    """
    Simulates the LangGraph workflow loop.
    """

    def __init__(self):
        self.decision_engine = DecisionEngine()
        self.education_crew = EducationCrew()
        self.monitor = MonitorAgent()

    def run_cycle(self, student_state: dict):
        print("\n--- New Cycle ---")
        print("Current State:", student_state)

        # 1. Decision Engine
        decision = self.decision_engine.decide_next_step(student_state)
        print("Decision:", decision)

        # 2. Education Crew (if routed there)
        if decision["next_node"] == "education_crew":
            state = {
                    "decision": decision,
                    "student_state": student_state
                    }

            state = self.education_crew.run(state)
            crew_output = state["crew_output"]

            
        else:
            crew_output = {"agent": "monitor_agent", "message": "No crew action required."}

        print("Crew Output:", crew_output)

        # 3. Monitor Interaction
        monitor_output = self.monitor.interact(crew_output, student_state)
        print("Monitor Output:", monitor_output)

        return monitor_output["updated_student_state"]
