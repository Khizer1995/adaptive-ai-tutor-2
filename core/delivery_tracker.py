from __future__ import annotations

from typing import Any, Dict, List, Set


def append_delivered_chunks(student_state: Dict[str, Any], topic: str, rag_chunk_records: List[Dict[str, Any]]) -> None:
    delivered = student_state.setdefault("delivered_chunks", {})
    topic_entry = delivered.setdefault(topic, {"chunk_ids": [], "concepts": []})

    existing_chunk_ids: Set[str] = set(topic_entry.get("chunk_ids", []))
    existing_concepts: Set[str] = set(topic_entry.get("concepts", []))

    for record in rag_chunk_records:
        chunk_id = str(record.get("chunk_id", "")).strip()
        metadata = record.get("metadata", {}) or {}
        concept = str(metadata.get("concept", "")).strip()

        if chunk_id and chunk_id not in existing_chunk_ids:
            topic_entry.setdefault("chunk_ids", []).append(chunk_id)
            existing_chunk_ids.add(chunk_id)
        if concept and concept not in existing_concepts:
            topic_entry.setdefault("concepts", []).append(concept)
            existing_concepts.add(concept)


def get_delivered_topic_summary(student_state: Dict[str, Any], topic: str) -> Dict[str, List[str]]:
    delivered = student_state.get("delivered_chunks", {}) or {}
    topic_entry = delivered.get(topic, {}) or {}
    return {
        "chunk_ids": list(topic_entry.get("chunk_ids", [])),
        "concepts": list(topic_entry.get("concepts", [])),
    }

