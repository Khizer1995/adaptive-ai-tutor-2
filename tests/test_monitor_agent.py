from core.monitor_agent import MonitorAgent

monitor = MonitorAgent()

crew_output = {
    "agent": "tutor_agent",
    "message": "Learning path adjusted."
}

student_state = {
    "last_score": 0.4,
    "engagement": "medium"
}

result = monitor.interact(crew_output, student_state)
print(result)
