"""
LangGraph Entry Point  —  Shazi's Work
Runs the compiled adaptive_graph with a student state.

Usage
-----
cd "c:\\Users\\mohammed shazi\\Desktop\\SEM6\\Capstone_project"
python run_langgraph.py
"""

from dotenv import load_dotenv
load_dotenv()

from typing import Dict, Any, cast
from core.langgraph_flow import adaptive_graph
from core.evaluation import evaluate_cycle
from core.logging_utils import Timer


def main():
    print("=" * 60)
    print("  Cognitive Adaptive AI Tutor — LangGraph Flow")
    print("=" * 60)

    # Initial student state
    initial_state = {
        "student_state": {
            "student_id": "KISH-001",
            "level": "beginner",
            "current_topic": None,
            "progress": [],
            "engagement": "medium",
            "last_score": 0.3,
            "learning_history": []
        },
        "decision": {},
        "crew_output": {},
        "rag_status": {}
    }

    print("\nInitial Student State:")
    for k, v in initial_state["student_state"].items():
        print(f"  {k}: {v}")

    print("\nRunning LangGraph adaptive flow...\n")

    try:
        t_flow = Timer()
        final_state = adaptive_graph.invoke(initial_state)
        flow_ms = round(t_flow.elapsed_ms(), 2)

        print("\n" + "=" * 60)
        print("FINAL STUDENT STATE:")
        print("=" * 60)
        for k, v in final_state["student_state"].items():
            print(f"  {k}: {v}")

        crew_out = cast(Dict[str, Any], final_state.get("crew_output", {}))
        if crew_out:
            print("\n--- Last Crew Output ---")
            print(f"  Teacher Style : {crew_out.get('teacher_style', 'N/A')}")
            print(f"  Quiz          : {crew_out.get('quiz', [])}")
            print(f"  Validation    : {crew_out.get('validation_status', 'N/A')}")
            synthesis = crew_out.get("learning_path", "")
            if synthesis and isinstance(synthesis, str):
                # Build snippet via loop to bypass strange IDE linting errors regarding indexing/slicing
                snippet_chars = []
                for i, char in enumerate(synthesis):
                    if i >= 500:
                        break
                    snippet_chars.append(char)
                snippet = "".join(snippet_chars)
                print(f"\n--- LLM Synthesis (first 500 chars) ---")
                print(snippet)

        # Lightweight evaluation summary for report logs
        evaluate_cycle(
            final_state.get("student_state", {}),
            final_state.get("decision", {}),
            final_state.get("crew_output", {}),
            {"langgraph_flow_ms": flow_ms},
        )
    except Exception as e:
        print(f"\n[ERROR] LangGraph flow failed: {e}")
        raise


if __name__ == "__main__":
    main()
