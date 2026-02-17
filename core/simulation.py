from core.decision_engine import DecisionEngine
from core.education_crew import EducationCrew
from core.monitor_agent import MonitorAgent


class AdaptiveLearningSimulation:
    """
    Simulates the adaptive workflow loop.
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

        # 2. Education Crew
        if decision["next_node"] == "education_crew":
            crew_output = self.education_crew.execute(
                decision,
                student_state
            )
        else:
            crew_output = {"message": "No crew action required."}

        print("Crew Output:", crew_output)

        # 3. Monitor Interaction
        monitor_output = self.monitor.interact(crew_output, student_state)
        print("Monitor Output:", monitor_output)

        return monitor_output["updated_student_state"]


# 🔥 ENTRY POINT ADDED
if __name__ == "__main__":

    simulation = AdaptiveLearningSimulation()

    # Initial student state
    student_state = {
    "level": "beginner",
    "current_topic": None,
    "progress": [],
    "engagement": "normal",
    "last_score": 0.3,
    "learning_history": []
}


    # Run 3 adaptive cycles
    for _ in range(3):
        student_state = simulation.run_cycle(student_state)

    print("\nFinal Student State:", student_state)
