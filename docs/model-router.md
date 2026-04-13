## Model Router Agent

This module adds multi-LLM routing between Gemini and Groq.

### Files
- `core/llm/router.py`: task routing, prompt standardization, fallback behavior
- `core/llm/gemini_client.py`: Gemini API client
- `core/llm/groq_client.py`: Groq API client

### Routing policy
- Gemini:
  - `deep_reasoning`
  - `concept_explanation`
  - `misconception_correction`
- Groq:
  - `quiz_generation`
  - `fast_response`
  - `basic_evaluation`

Fallback:
- If Gemini fails, router automatically retries with Groq.

### Input/Output contract

Input:
- `task_type` (string)
- `user_query` (string)
- `context` (optional string)
- `output_schema` (optional dict for structured fields)

Output:
```python
{
  "task_type": "...",
  "selected_provider": "gemini|groq|groq_fallback",
  "content": "...",
  "provider_metadata": {
    "provider": "gemini|groq",
    "model": "..."
  }
}
```

### Integration with Retrieval Agent + Tutor Agent

`TutorAgent.generate_learning_path()` already:
1. Retrieves chunks via `Retriever`
2. Builds `context` from retrieved chunks
3. Calls router with task type `concept_explanation`

This preserves RAG grounding while shifting model selection into the router.

### Integration with quiz generation

`PracticalAgent.generate_quiz()` now calls router with:
- `task_type="quiz_generation"` (routes to Groq)
- fallback to existing deterministic quiz logic if call fails.

### Environment variables

Set in `.env`:
- `GEMINI_API_KEY`
- `GROQ_API_KEY`
