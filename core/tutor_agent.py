class TutorAgent:
    """
    Context-aware adaptive tutor.
    Uses student history to avoid repetition
    and escalate curriculum intelligently.
    """

    curriculum = [
        "Python variables",
        "Control flow (if/else)",
        "Loops",
        "Functions",
        "Lists and arrays",
        "Recursion",
        "Sorting algorithms",
        "Binary search",
        "Dynamic programming basics"
    ]

    def get_next_topic(self, student_state):

        progress = student_state.get("progress", [])

        for topic in self.curriculum:
            if topic not in progress:
                return topic

        return "Advanced problem solving"

    def generate_learning_path(self, decision_output: dict, student_state: dict):

        level = student_state.get("level", "beginner")
        action = decision_output.get("action", "default")

        # Determine topic
        topic = student_state.get("current_topic")

        if not topic:
            topic = self.get_next_topic(student_state)
            student_state["current_topic"] = topic  # Persist topic

        # Only regenerate full learning path if adjusting path
        if action == "adjust_learning_path":

            if level == "beginner":
                path = [
                    f"Concept overview of {topic}",
                    f"Simple examples of {topic}",
                    f"Guided practice for {topic}"
                ]

            elif level == "intermediate":
                path = [
                    f"Deep dive into {topic}",
                    f"Edge cases in {topic}",
                    f"Problem solving exercises for {topic}"
                ]

            else:
                path = [
                    f"Advanced patterns using {topic}",
                    f"Optimization techniques in {topic}",
                    f"Real-world applications of {topic}"
                ]

        else:
            # If not adjusting path, keep minimal structure
            path = [f"Continued practice for {topic}"]

        if action == "increase_support":
            path.insert(0, f"Fundamental recap of {topic}")

        return path
