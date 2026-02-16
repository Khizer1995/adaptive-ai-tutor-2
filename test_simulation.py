from core.simulation import AdaptiveLearningSimulation

simulation = AdaptiveLearningSimulation()

student_state = {
    "level": "beginner",
    "progress": [],
    "engagement": "normal"
}

updated_state = simulation.run_cycle(student_state)

print("\nUpdated State:", updated_state)
