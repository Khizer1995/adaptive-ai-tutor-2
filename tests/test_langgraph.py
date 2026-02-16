from core.langgraph_flow import adaptive_graph

initial_state = {
    "student_state": {
        "level": "beginner",
        "progress": [],
        "engagement": "normal"
    }
}

print("Initial state:", initial_state)

result = adaptive_graph.invoke(initial_state)

print("\nFinal result:", result)
