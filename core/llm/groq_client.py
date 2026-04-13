import os
from typing import Any, Dict


class GroqClient:
    def __init__(self, model: str = "llama-3.1-8b-instant"):
        try:
            from dotenv import load_dotenv
            load_dotenv()
        except Exception:
            pass

        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY not set in .env")
        self.model = model
        self.api_key = api_key

        try:
            from groq import Groq  # type: ignore
        except Exception as exc:
            raise ImportError(
                "groq package is not installed. Add 'groq>=0.9.0' to requirements."
            ) from exc

        self._client = Groq(api_key=self.api_key)

    def generate(self, prompt: str, task_type: str) -> Dict[str, Any]:
        completion = self._client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are a concise educational assistant."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
        )
        content = completion.choices[0].message.content or ""
        return {
            "provider": "groq",
            "model": self.model,
            "task_type": task_type,
            "content": content,
        }
