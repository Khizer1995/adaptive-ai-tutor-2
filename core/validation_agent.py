class ValidationAgent:
    """
    Validation Agent

    Responsible for validating generated educational content
    before delivery to student.
    """

    def validate_content(self, crew_output: dict):

        # baseline academic reproduction:
        # simple pass-through validation

        validated_output = crew_output.copy()

        # Example rule (can expand later)
        if not validated_output.get("learning_path"):
            validated_output["validation_status"] = "failed"
        else:
            validated_output["validation_status"] = "passed"

        return validated_output
