from core.education_crew import EducationCrew

# simulate decision engine output
decision_output = {
    "topic": "Python Basics"
}

# simulate student state
student_state = {
    "level": "beginner"
}

crew = EducationCrew()

result = crew.execute(decision_output, student_state)

print(result)
