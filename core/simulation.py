from dotenv import load_dotenv
import os

load_dotenv()

from .decision_engine import DecisionEngine
from .education_crew import EducationCrew
from .monitor_agent import MonitorAgent
from .validation_agent import ValidationAgent
from .teacher_review_agent import TeacherReviewAgent
from .profile_manager import ProfileManager
from .file_manager_agent import FileManagerAgent
from .evaluation import evaluate_cycle
from .logging_utils import Timer
from .learning_record import log_state_learning_record
from .knowledge_state_updater import apply_execution_feedback, ensure_knowledge_state
from .metrics_collector import log_learning_cycle_metrics


class AdaptiveLearningSimulation:
    """
    Simulates the adaptive learning workflow loop.
    """

    def __init__(self):
        self.decision_engine = DecisionEngine()
        self.education_crew = EducationCrew()
        self.monitor = MonitorAgent()
        self.profile_manager = ProfileManager()
        self.validation = ValidationAgent()
        self.teacher_review = TeacherReviewAgent()

    def run_cycle(self, student_state: dict) -> dict:
        t_e2e = Timer()
        print("\n--- New Cycle ---")
        print(f"Level      : {student_state.get('level')}")
        print(f"Topic      : {student_state.get('current_topic')}")
        print(f"Score      : {student_state.get('last_score')}")
        print(f"Engagement : {student_state.get('engagement')}")

        student_state = ensure_knowledge_state(student_state)

        # 1. Macro + micro decisions
        macro = self.decision_engine.decide_macro_plan(student_state)
        student_state["macro_decision"] = macro
        t_decision = Timer()
        decision = self.decision_engine.decide_next_step(student_state)
        decision_ms = round(t_decision.elapsed_ms(), 2)
        print(f"Decision   : {decision}")

        # 2. Education Crew
        crew_ms = 0.0
        crew_output = {"message": "No crew action required."}
        if decision.get("next_node") == "education_crew":
            t_crew = Timer()
            crew_state = self.education_crew.run(
                {"decision": decision, "student_state": student_state}
            )
            proposals = crew_state.get("crew_proposals", [])
            crew_output = self.decision_engine.arbitrate_crew_proposals(
                decision, proposals, student_state
            )
            crew_ms = round(t_crew.elapsed_ms(), 2)

        # 3. Validation
        crew_output = self.validation.validate_content(crew_output, student_state)

        # 4. Teacher review (CLI)
        review = self.teacher_review.review(crew_output, student_state)
        if review.get("review_status") != "approved":
            return student_state
        log_state_learning_record(
            {
                "student_state": student_state,
                "crew_output": crew_output,
                "decision": decision,
                "teacher_review": review,
            }
        )

        # 5. Monitor Interaction
        t_monitor = Timer()
        monitor_output = self.monitor.interact(
            crew_output,
            student_state
        )
        monitor_ms = round(t_monitor.elapsed_ms(), 2)
        print(f"Monitor    : {monitor_output.get('feedback')}")

        # --- Metrics Calculation ---
        updated_state = monitor_output.get("updated_student_state", student_state)
        updated_state = apply_execution_feedback(
            updated_state,
            monitor_output.get("execution_feedback", {}),
            macro,
        )

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


        evaluate_cycle(
            updated_state,
            decision,
            crew_output,
            {
                "decision_ms": decision_ms,
                "crew_ms": crew_ms,
                "monitor_ms": monitor_ms,
            },
        )
        log_learning_cycle_metrics(
            student_state=updated_state,
            macro_decision=macro,
            micro_decision=decision,
            crew_output=crew_output,
            timings={
                "rag_latency_ms": 0.0,
                "crewai_latency_ms": crew_ms,
                "e2e_latency_ms": round(t_e2e.elapsed_ms(), 2),
            },
            rag_chunk_records=crew_output.get("rag_chunk_records", []) or [],
            decision_iterations=1,
        )

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
    file_manager = FileManagerAgent()

    file_manager.prepare_knowledge_base()

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
