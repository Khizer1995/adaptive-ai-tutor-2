class TeacherPersonaAgent:
    """
    Selects adaptive teaching style based on
    student performance and engagement.
    """

    def apply_persona(self, student_state: dict):

        score = student_state.get("last_score", 0)
        engagement = student_state.get("engagement", "medium")

        # Struggling student → supportive tutor
        if score < 0.5 or engagement == "low":
            return (
                "Supportive Tutor: Explain slowly, use simple language, "
                "provide multiple examples, encourage confidence."
            )

        # Medium progress → balanced coach
        if 0.5 <= score <= 0.8:
            return (
                "Balanced Coach: Provide structured explanations, "
                "guided exercises, and incremental challenges."
            )

        # High performer → challenging mentor
        if score > 0.8:
            return (
                "Challenging Mentor: Use concise explanations, "
                "introduce advanced insights, and harder problems."
            )

        return "Default teaching style."
