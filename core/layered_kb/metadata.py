from __future__ import annotations

from typing import List

from core.layered_kb.schema import KBChunk


class MetadataIntelligence:
    def enrich(self, chunks: List[KBChunk]) -> List[KBChunk]:
        enriched: List[KBChunk] = []
        for chunk in chunks:
            chunk.source_priority = self._source_priority(chunk.source, chunk.difficulty)
            enriched.append(chunk)
        return enriched

    @staticmethod
    def _source_priority(source: str, difficulty: str) -> int:
        if source == "opendsa":
            if difficulty == "beginner":
                return 4
            return 3
        if difficulty == "beginner":
            return 2
        return 3

