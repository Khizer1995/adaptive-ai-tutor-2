from __future__ import annotations

from typing import Any, Dict, List, Optional

import chromadb

from core.layered_kb.schema import KBChunk


class LayeredVectorStore:
    def __init__(
        self,
        persist_directory: str = "data/vector_db_layered",
        collection_name: str = "layered_dsa_kb",
    ) -> None:
        self.client = chromadb.PersistentClient(path=persist_directory)
        self.collection = self.client.get_or_create_collection(name=collection_name)

    def upsert_chunks(self, chunks: List[KBChunk], embeddings: List[List[float]]) -> None:
        ids = [c.chunk_id for c in chunks]
        docs = [c.content for c in chunks]
        metas = [c.to_metadata() for c in chunks]
        self.collection.upsert(ids=ids, embeddings=embeddings, documents=docs, metadatas=metas)

    def query(
        self,
        query_embedding: List[float],
        k: int = 12,
        where: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        kwargs: Dict[str, Any] = {"query_embeddings": [query_embedding], "n_results": k}
        if where:
            kwargs["where"] = where
        return self.collection.query(**kwargs)

