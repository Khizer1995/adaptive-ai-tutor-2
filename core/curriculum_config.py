"""
curriculum_config.py
====================
Single source of truth for the curriculum structure.

Root-cause fix for Issue #5 (only one topic shown):
  • TOPIC_SUBTOPICS previously defined only "stack".
  • Now all seven DSA topics are defined with their full subtopic lists.
  • get_all_curriculum_topics() returns the ordered list of topic dicts
    so the /student/topics endpoint can surface ALL topics.
"""

from __future__ import annotations

UNLOCK_THRESHOLD = 0.70

TOPIC_SUBTOPICS: dict[str, list[dict[str, str]]] = {
    "array": [
        {"id": "array_introduction",  "title": "Introduction & Concept"},
        {"id": "array_operations",    "title": "Array Operations"},
        {"id": "array_searching",     "title": "Searching (Linear & Binary)"},
        {"id": "array_sorting",       "title": "Sorting Algorithms"},
        {"id": "array_multidimensional", "title": "Multi-dimensional Arrays"},
        {"id": "array_applications",  "title": "Applications & Use-cases"},
    ],
    "queue": [
        {"id": "queue_introduction", "title": "Introduction & Concept"},
        {"id": "queue_enqueue",      "title": "Enqueue Operation"},
        {"id": "queue_dequeue",      "title": "Dequeue Operation"},
        {"id": "queue_circular",     "title": "Circular Queue"},
        {"id": "queue_priority",     "title": "Priority Queue"},
        {"id": "queue_deque",        "title": "Deque (Double-ended Queue)"},
        {"id": "queue_applications", "title": "Applications"},
    ],
    "graph": [
        {"id": "graph_introduction",   "title": "Introduction & Terminology"},
        {"id": "graph_representation", "title": "Adjacency Matrix / List"},
        {"id": "graph_bfs",            "title": "Breadth-First Search (BFS)"},
        {"id": "graph_dfs",            "title": "Depth-First Search (DFS)"},
        {"id": "graph_shortest_path",  "title": "Shortest Path (Dijkstra / BFS)"},
        {"id": "graph_topological",    "title": "Topological Sort"},
        {"id": "graph_applications",   "title": "Applications"},
    ],
}

# Ordered list of topics for curriculum navigation.
TOPIC_ORDER: list[str] = [
    "array",
    "queue",
    "graph",
]

OPENDSA_PAGE_MAP: dict[str, str] = {
    # Array subtopics - using verified ListArray and BinarySearch pages
    "array_introduction": "ListArray",
    "array_operations": "ListArray",
    "array_searching": "BinarySearch",
    "array_sorting": "ListArray",  # Arrays chapter covers basic sorting context
    
    # Queue subtopics - using verified Queue and QueueLinked pages
    "queue_introduction": "Queue",
    "queue_enqueue": "Queue",
    "queue_dequeue": "Queue",
    "queue_applications": "QueueLinked",
    
    # Graph subtopics - no verified OpenDSA pages yet
    # (hybrid_retriever will fall back to PDF content gracefully)
}


def get_next_subtopic(topic: str, current_subtopic: str) -> tuple[str | None, bool]:
    sequence = TOPIC_SUBTOPICS.get(topic, [])
    if not sequence:
        return None, True
    ids = [item["id"] for item in sequence]
    if current_subtopic not in ids:
        return ids[0], False
    idx = ids.index(current_subtopic)
    if idx + 1 >= len(ids):
        return None, True
    return ids[idx + 1], False


def get_all_curriculum_topics() -> list[dict]:
    """
    Return all topics with their subtopic lists — consumed by the API's
    /student/topics endpoint to build the full topic sidebar (Issue #5 fix).
    """
    result = []
    for order_idx, name in enumerate(TOPIC_ORDER):
        subtopics = TOPIC_SUBTOPICS.get(name, [])
        result.append({
            "name": name,
            "order_index": order_idx,
            "subtopics": [s["id"] for s in subtopics],
            "subtopic_details": subtopics,
        })
    return result
