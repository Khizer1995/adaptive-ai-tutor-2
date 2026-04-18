from __future__ import annotations

import hashlib
import math
import re
import warnings

from sentence_transformers import SentenceTransformer


class LocalEmbeddingModel:
    """
    Local embedding model using sentence-transformers
    """

    def __init__(self):
        self.model = None
        self.dim = 384
        try:
            # Prefer local cache; avoids slow startup when network/proxy is unavailable.
            self.model = SentenceTransformer("all-MiniLM-L6-v2", local_files_only=True)
        except Exception as exc:
            warnings.warn(
                f"Falling back to deterministic hash embeddings (offline mode). reason={exc}",
                RuntimeWarning,
            )

    def embed(self, text: str):
        if self.model is not None:
            return self.model.encode(text).tolist()
        return self._hash_embed(text)

    def _hash_embed(self, text: str):
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
