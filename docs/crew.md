## Education Crew

The Education Crew is orchestrated as a single node in LangGraph but internally
coordinates three agents:

- Tutor Agent: produces learning content using RAG + Gemini.
- Practical Agent: generates adaptive quizzes.
- Teacher Persona Agent: selects teaching style for delivery.

Logs: `logs/crew.log` includes per-cycle outputs for content and quizzes.
