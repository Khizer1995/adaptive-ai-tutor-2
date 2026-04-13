class PracticalAgent:
    """
    Generates adaptive quizzes based on
    topic and student level.
    """

    def generate_quiz(self, decision_output: dict, student_state: dict):
        from core.logging_utils import get_logger, trace_event
        from core.llm.router import ModelRouterAgent
        import json
        logger = get_logger("practical_agent", "crew.log")
        router = ModelRouterAgent()

        topic = student_state.get("current_topic", "Python variables")
        level = student_state.get("level", "beginner")
        style = student_state.get("learning_style", "balanced")

        fallback_quiz = []

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
        fallback_quiz = quiz

        try:
            routed = router.route(
                task_type="quiz_generation",
                user_query=(
                    f"Create 3 adaptive quiz questions for topic '{topic}' at {level} level "
                    f"for a {style} learner."
                ),
                context=f"Decision action: {decision_output.get('action', 'unknown')}",
                output_schema={
                    "quiz": "array with 3 questions",
                    "answer_outline": "brief expected answer hints",
                },
            )
            content = routed.get("content", "").strip()
            if content:
                parsed_quiz = None
                if content.startswith("{") or content.startswith("["):
                    try:
                        payload = json.loads(content)
                        if isinstance(payload, dict):
                            parsed_quiz = payload.get("quiz")
                        elif isinstance(payload, list):
                            parsed_quiz = payload
                    except Exception:
                        parsed_quiz = None

                if isinstance(parsed_quiz, list):
                    quiz = [str(item).strip() for item in parsed_quiz if str(item).strip()][:3]
                else:
                    quiz = [line.strip("- ").strip() for line in content.splitlines() if line.strip()][:3]
                quiz = quiz if len(quiz) == 3 else fallback_quiz
            else:
                quiz = fallback_quiz
        except Exception as exc:
            logger.warning(f"groq_quiz_fallback error={exc}")
            quiz = fallback_quiz

        logger.info(f"topic='{topic}' level={level} style={style} quiz_len={len(quiz)}")
        trace_event(
            "quiz_generated",
            {"topic": topic, "level": level, "style": style, "quiz_len": len(quiz)},
        )
        return quiz
