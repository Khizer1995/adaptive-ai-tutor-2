from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional


@dataclass
class KBChunk:
    chunk_id: str
    topic: str
    concept: str
    source: str
    difficulty: str
    content_type: str
    content: str
    source_priority: int
    source_ref: str
    layer: str
    title: str
    order_index: int = 0

    def to_metadata(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["type"] = payload.pop("content_type")
        payload.pop("content")
        return payload

    def to_payload(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["type"] = payload.pop("content_type")
        return payload


@dataclass
class StudentState:
    topic: str
    student_mastery: float
    confidence: float
    learning_trend: str = "steady"
    engagement: Optional[float] = None
    learning_gain: Optional[float] = None

