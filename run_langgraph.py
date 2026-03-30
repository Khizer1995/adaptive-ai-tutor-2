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
        "crew_output": {}
    }

    print("\nInitial Student State:")
    for k, v in initial_state["student_state"].items():
        print(f"  {k}: {v}")

    print("\nRunning LangGraph adaptive flow...\n")

    try:
        final_state = adaptive_graph.invoke(initial_state)

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
    except Exception as e:
        print(f"\n[ERROR] LangGraph flow failed: {e}")
        raise


if __name__ == "__main__":
    main()
