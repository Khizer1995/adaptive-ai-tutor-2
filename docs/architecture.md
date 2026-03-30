## Architecture Overview

This system follows the AIA-PAL style architecture from the reference paper:

- LangGraph as the core decision engine.
- Education Crew (Tutor, Practical, Teacher Persona) as a single LangGraph node.
- Monitor Agent as the delivery and feedback node.
- File Manager Agent to prepare the RAG knowledge base.
- Student Profile Agent to persist learning state.

The runtime flow is:

1. File Manager prepares the RAG store from teacher-provided PDFs.
2. Decision Engine routes learning actions based on student state.
3. Education Crew generates learning content and quizzes.
4. Validation Agent checks learning output.
5. Monitor Agent updates student performance and engagement.
6. Student Profile Agent saves the updated profile.

Trace logs and evaluation logs are written to the `logs/` folder.
