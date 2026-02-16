class PracticalAgent:
    """
    Practical Agent:
    Responsible for generating practice quizzes
    based on learning path or topic.
    """

    def generate_quiz(self, decision_output: dict, student_state: dict):

        topic = decision_output.get("topic", "general topic")

        quiz = [
            f"What is the main concept of {topic}?",
            f"Explain key principles of {topic}.",
            f"Give an example related to {topic}."
        ]

        return quiz
