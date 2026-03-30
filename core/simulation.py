from dotenv import load_dotenv
import os

load_dotenv()

from .decision_engine import DecisionEngine
from .education_crew import EducationCrew
from .monitor_agent import MonitorAgent
from .profile_manager import ProfileManager


class AdaptiveLearningSimulation:
    """
    Simulates the adaptive learning workflow loop.
    """

    def __init__(self):
        self.decision_engine = DecisionEngine()
        self.education_crew = EducationCrew()
        self.monitor = MonitorAgent()
        self.profile_manager = ProfileManager()

    def run_cycle(self, student_state: dict) -> dict:
        print("\n--- New Cycle ---")
        print(f"Level      : {student_state.get('level')}")
        print(f"Topic      : {student_state.get('current_topic')}")
        print(f"Score      : {student_state.get('last_score')}")
        print(f"Engagement : {student_state.get('engagement')}")

        # 1. Decision Engine
        decision = self.decision_engine.decide_next_step(student_state)
        print(f"Decision   : {decision}")

        # 2. Education Crew
        crew_output = (
            self.education_crew.execute(decision, student_state)
            if decision.get("next_node") == "education_crew"
            else {"message": "No crew action required."}
        )

        # Show LLM synthesis snippet (clean slicing)
        synthesis = crew_output.get("learning_path", "")
        if isinstance(synthesis, str) and synthesis:
            snippet = synthesis[:300]
            print(f"\n[LLM Synthesis]\n{snippet}...\n")

        # 3. Monitor Interaction
        monitor_output = self.monitor.interact(
            {"decision": decision, **crew_output},
            student_state
        )
        print(f"Monitor    : {monitor_output.get('feedback')}")

        # --- Metrics Calculation ---
        updated_state = monitor_output.get("updated_student_state", student_state)

        # Learning Gain: difference between last two scores
        lh = updated_state.get("learning_history", [])
        if len(lh) >= 2:
            gain = lh[-1]["score"] - lh[-2]["score"]
        else:
            gain = 0.0
        updated_state.setdefault("learning_gain_history", []).append(gain)

        # Accuracy: proportion of scores >= 0.75 (mastery threshold)
        scores = [h["score"] for h in lh]
        if scores:
            accuracy = sum(1 for s in scores if s >= 0.75) / len(scores)
        else:
            accuracy = 0.0
        updated_state.setdefault("accuracy_history", []).append(accuracy)

        # Engagement Score: map engagement string to int (low=3, medium=6, high=9)
        engagement_map = {"low": 3, "medium": 6, "high": 9}
        engagement_str = updated_state.get("engagement", "medium")
        engagement_score = engagement_map.get(engagement_str, 6)
        updated_state.setdefault("engagement_score_history", []).append(engagement_score)

        print(f"Learning Gain (this cycle): {gain:.2f}")
        print(f"Accuracy (so far): {accuracy:.2f}")
        print(f"Engagement Score (this cycle): {engagement_score}")

        return updated_state


def load_or_initialize_profile(pm: ProfileManager):
    try:
        student_state = pm.load("KISH-001")
        print(f"[ProfileManager] Loaded profile: {student_state['name']} ({student_state['student_id']})")
    except FileNotFoundError:
        student_state = {
            "student_id": "KISH-001",
            "name": "Kishore",
            "level": "beginner",
            "current_topic": None,
            "progress": [],
            "engagement": "medium",
            "last_score": 0.3,
            "learning_history": []
        }
        print("[ProfileManager] No profile found, using default state.")

    return student_state


def main():
    simulation = AdaptiveLearningSimulation()
    pm = ProfileManager()

    student_state = load_or_initialize_profile(pm)

    print("\n" + "=" * 60)
    print("ADAPTIVE LEARNING SIMULATION (3 cycles)")
    print("=" * 60)

    for cycle in range(3):
        print(f"\n{'='*20} CYCLE {cycle+1} {'='*20}")
        student_state = simulation.run_cycle(student_state)
        # Persist metrics after each cycle
        pm.save("KISH-001", student_state)

    print("\n" + "=" * 60)
    print("FINAL STUDENT STATE:")
    for k, v in student_state.items():
        if k != "learning_history":
            print(f"{k}: {v}")
    print(f"learning_history ({len(student_state.get('learning_history', []))} entries)")

    # --- Metrics Visualization ---
    lg_hist = student_state.get("learning_gain_history", [])
    acc_hist = student_state.get("accuracy_history", [])
    eng_hist = student_state.get("engagement_score_history", [])
    print("\nLearning Gain History:")
    print(lg_hist)
    print("Accuracy History:")
    print(acc_hist)
    print("Engagement Score History:")
    print(eng_hist)

    pm.save("KISH-001", student_state)


if __name__ == "__main__":
    main()