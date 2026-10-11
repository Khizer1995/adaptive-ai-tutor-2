from __future__ import annotations

from collections import defaultdict
from typing import Dict, List

from core.layered_kb.schema import KBChunk


DEFAULT_PREREQS = {
    "array": [],
    "queue": ["array"],
    "graph": ["queue"],
}


def build_topic_dependency_graph(chunks: List[KBChunk]) -> Dict[str, Dict[str, List[str]]]:
    topic_order: Dict[str, int] = {}
    for chunk in chunks:
        if chunk.topic not in topic_order:
            topic_order[chunk.topic] = chunk.order_index
        else:
            topic_order[chunk.topic] = min(topic_order[chunk.topic], chunk.order_index)

    sorted_topics = sorted(topic_order.items(), key=lambda x: x[1])
    names = [t for t, _ in sorted_topics]
    next_map = defaultdict(list)
    for idx, topic in enumerate(names):
        if idx + 1 < len(names):
            next_map[topic].append(names[idx + 1])

    graph: Dict[str, Dict[str, List[str]]] = {}
    for topic in names:
        graph[topic] = {
            "prerequisites": DEFAULT_PREREQS.get(topic, []),
            "next_topics": next_map.get(topic, []),
        }
    return graph

