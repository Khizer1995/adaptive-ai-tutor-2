## Prompt Documentation

Tutor Agent prompt template (high level):

- System: "You are a helpful Python tutor."
- Inputs: level, topic, learning style, learning goal, retrieved RAG chunks.
- Output format:
  - Simple explanation
  - Code examples
  - Key takeaways

Teacher Persona Agent:
- Supportive Tutor (low score/engagement)
- Balanced Coach (medium performance)
- Challenging Mentor (high performance)

Practical Agent:
- Quiz questions vary by level and learning style.
