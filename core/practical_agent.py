class PracticalAgent:
    """
    Generates adaptive quizzes based on
    topic and student level.
    """

    def generate_quiz(self, decision_output: dict, student_state: dict):

        topic = student_state.get("current_topic", "Python variables")
        level = student_state.get("level", "beginner")

        if level == "beginner":
            quiz = [
                f"What is {topic}?",
                f"Write a simple example of {topic}.",
                f"When would you use {topic}?"
            ]

        elif level == "intermediate":
            quiz = [
                f"Explain edge cases in {topic}.",
                f"Compare {topic} with a related concept.",
                f"Solve a moderate problem using {topic}."
            ]

        else:
            quiz = [
                f"Optimize an implementation involving {topic}.",
                f"Discuss performance trade-offs in {topic}.",
                f"Design a system using {topic}."
            ]

        return quiz
