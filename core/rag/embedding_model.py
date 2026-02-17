import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))


class GeminiEmbeddingModel:
    """
    Wrapper for Gemini embedding model
    """

    def __init__(self):
        self.model = "models/embedding-001"

    def embed(self, text: str):
        response = genai.embed_content(
            model=self.model,
            content=text,
            task_type="retrieval_document"
        )
        return response["embedding"]
