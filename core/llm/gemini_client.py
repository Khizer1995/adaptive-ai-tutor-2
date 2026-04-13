import os
from typing import Any, Dict


class GeminiClient:
    def __init__(self, model: str = "gemini-2.0-flash-lite"):
        try:
            from dotenv import load_dotenv
            load_dotenv()
        except Exception:
            pass

        from google import genai

        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY not set in .env")
        self.model = model
        self.client = genai.Client(api_key=api_key)

    def generate(self, prompt: str, task_type: str) -> Dict[str, Any]:
        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
        )
        text = response.text or ""
        return {
            "provider": "gemini",
            "model": self.model,
            "task_type": task_type,
            "content": text,
        }
