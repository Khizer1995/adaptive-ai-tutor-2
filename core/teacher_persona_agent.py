class TeacherPersonaAgent:
    """
    Selects adaptive teaching style based on
    student performance and engagement.
    """

    def apply_persona(self, student_state: dict):
        from core.logging_utils import get_logger, trace_event
        logger = get_logger("teacher_persona", "crew.log")

        score = student_state.get("last_score", 0)
        engagement = student_state.get("engagement", "medium")

        # Struggling student → supportive tutor
        if score < 0.5 or engagement == "low":
            persona = (
                "Supportive Tutor: Explain slowly, use simple language, "
                "provide multiple examples, encourage confidence."
            )
            logger.info(f"persona='supportive' score={score} engagement={engagement}")
            trace_event("persona_selected", {"persona": "supportive"})
            return persona

        # Medium progress → balanced coach
        if 0.5 <= score <= 0.8:
            persona = (
                "Balanced Coach: Provide structured explanations, "
                "guided exercises, and incremental challenges."
            )
            logger.info(f"persona='balanced' score={score} engagement={engagement}")
            trace_event("persona_selected", {"persona": "balanced"})
            return persona

        # High performer → challenging mentor
        if score > 0.8:
            persona = (
                "Challenging Mentor: Use concise explanations, "
                "introduce advanced insights, and harder problems."
            )
            logger.info(f"persona='challenging' score={score} engagement={engagement}")
            trace_event("persona_selected", {"persona": "challenging"})
            return persona

        logger.info(f"persona='default' score={score} engagement={engagement}")
        trace_event("persona_selected", {"persona": "default"})
        return "Default teaching style."
