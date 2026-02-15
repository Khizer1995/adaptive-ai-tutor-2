from core.simulation import AdaptiveLearningSimulation

sim = AdaptiveLearningSimulation()

student_state = {
    "last_score": 0.4,
    "engagement": "medium"
}

for i in range(3):
    student_state = sim.run_cycle(student_state)
