from core.education_crew import EducationCrew

crew = EducationCrew()

decision_output = {"action": "adjust_learning_path"}
student_state = {"last_score": 0.3}

result = crew.execute(decision_output, student_state)
print(result)
