from core.rag.retriever import Retriever


class TutorAgent:
    """
    Context-aware adaptive RAG tutor.
    Uses curriculum progression + retrieval.
    """

    def __init__(self):
        self.retriever = Retriever()

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
            student_state["current_topic"] = topic

        # 🔥 Build adaptive query for RAG
        if action == "increase_support":
            query = f"Explain {topic} in simple terms for beginner with examples"
        elif level == "advanced":
            query = f"Provide deep technical explanation and edge cases for {topic}"
        else:
            query = f"Explain {topic} for {level} level student with examples"

        # 🔥 Retrieve from vector DB
        retrieved_chunks = self.retriever.retrieve(query, k=3)

        return retrieved_chunks
