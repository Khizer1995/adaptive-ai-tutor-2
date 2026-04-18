from __future__ import annotations

import os
from typing import List

from sentence_transformers import SentenceTransformer


class EmbeddingProvider:
    def embed(self, text: str) -> List[float]:
        raise NotImplementedError


class SentenceTransformerEmbedding(EmbeddingProvider):
    def __init__(self, model_name: str = "all-MiniLM-L6-v2") -> None:
        self.model = SentenceTransformer(model_name)

    def embed(self, text: str) -> List[float]:
        vector = self.model.encode(text, normalize_embeddings=True)
        return vector.tolist()


class GeminiEmbedding(EmbeddingProvider):
    def __init__(self, model_name: str = "models/text-embedding-004") -> None:
        import google.generativeai as genai

        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY not set for Gemini embeddings.")
        genai.configure(api_key=api_key)
        self.genai = genai
        self.model_name = model_name

    def embed(self, text: str) -> List[float]:
        response = self.genai.embed_content(model=self.model_name, content=text)
        return list(response["embedding"])


def build_embedder(provider: str = "sentence-transformers") -> EmbeddingProvider:
    if provider.lower() == "gemini":
        return GeminiEmbedding()
    return SentenceTransformerEmbedding()

