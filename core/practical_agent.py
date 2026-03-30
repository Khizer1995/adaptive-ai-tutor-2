class PracticalAgent:
    """
    Generates adaptive quizzes based on
    topic and student level.
    """

    def generate_quiz(self, decision_output: dict, student_state: dict):
        topic = student_state.get("current_topic", "Python variables")
        level = student_state.get("level", "beginner")
        style = student_state.get("learning_style", "balanced")

        if style == "visual":
            quiz = [
                f"Draw a diagram to explain {topic}.",
                f"Label the parts of {topic} visually.",
                f"Match the following visual representations to their code for {topic}."
            ]
        elif style == "problem-solver":
            quiz = [
                f"Solve this problem using {topic}.",
                f"Debug the following code related to {topic}.",
                f"Write a function that uses {topic} to achieve a goal."
            ]
        else:  # balanced or fallback
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
