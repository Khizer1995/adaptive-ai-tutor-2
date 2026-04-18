from __future__ import annotations

import os
import hashlib
import math
import re
import warnings
from typing import List

from sentence_transformers import SentenceTransformer


class EmbeddingProvider:
    def embed(self, text: str) -> List[float]:
        raise NotImplementedError


class SentenceTransformerEmbedding(EmbeddingProvider):
    def __init__(self, model_name: str = "all-MiniLM-L6-v2") -> None:
        self.model = None
        self.dim = 384
        try:
            self.model = SentenceTransformer(model_name, local_files_only=True)
        except Exception as exc:
            warnings.warn(
                f"Layered KB embedder using hash fallback (offline mode). reason={exc}",
                RuntimeWarning,
            )

    def embed(self, text: str) -> List[float]:
        if self.model is not None:
            vector = self.model.encode(text, normalize_embeddings=True)
            return vector.tolist()
        return self._hash_embed(text)

    def _hash_embed(self, text: str) -> List[float]:
        vec = [0.0] * self.dim
        tokens = re.findall(r"[a-zA-Z0-9_]+", (text or "").lower())
        if not tokens:
            return vec

        for token in tokens:
            digest = hashlib.sha1(token.encode("utf-8")).digest()
            idx = int.from_bytes(digest[:4], "big") % self.dim
            sign = 1.0 if (digest[4] % 2 == 0) else -1.0
            vec[idx] += sign

        norm = math.sqrt(sum(v * v for v in vec))
        if norm > 0:
            vec = [v / norm for v in vec]
        return vec


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

