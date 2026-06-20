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
    "linked_list": [
        {"id": "linked_list_introduction", "title": "Introduction & Concept"},
        {"id": "linked_list_insertion",    "title": "Insertion Operations"},
        {"id": "linked_list_deletion",     "title": "Deletion Operations"},
        {"id": "linked_list_traversal",    "title": "Traversal & Search"},
        {"id": "linked_list_doubly",       "title": "Doubly Linked List"},
        {"id": "linked_list_circular",     "title": "Circular Linked List"},
        {"id": "linked_list_applications", "title": "Applications"},
    ],
    "stack": [
        {"id": "stack_introduction",     "title": "Introduction & Concept"},
        {"id": "stack_push",             "title": "Push Operation"},
        {"id": "stack_pop",              "title": "Pop Operation"},
        {"id": "stack_peek",             "title": "Peek Operation"},
        {"id": "stack_isempty_isfull",   "title": "isEmpty / isFull"},
        {"id": "stack_array",            "title": "Stack using Array"},
        {"id": "stack_linked_list",      "title": "Stack using Linked List"},
        {"id": "stack_applications",     "title": "Applications (expression evaluation, backtracking)"},
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
    "hash_table": [
        {"id": "hash_table_introduction", "title": "Introduction & Concept"},
        {"id": "hash_functions",          "title": "Hash Functions"},
        {"id": "collision_chaining",      "title": "Collision: Chaining"},
        {"id": "collision_open",          "title": "Collision: Open Addressing"},
        {"id": "hash_table_operations",   "title": "Insert / Search / Delete"},
        {"id": "hash_table_applications", "title": "Applications"},
    ],
    "tree": [
        {"id": "tree_introduction",  "title": "Introduction & Terminology"},
        {"id": "binary_tree",        "title": "Binary Tree"},
        {"id": "bst_operations",     "title": "Binary Search Tree Operations"},
        {"id": "tree_traversal",     "title": "Tree Traversal (In/Pre/Post/Level)"},
        {"id": "balanced_trees",     "title": "Balanced Trees (AVL / RB-tree)"},
        {"id": "heap",               "title": "Heap & Priority Queue"},
        {"id": "tree_applications",  "title": "Applications"},
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
    "linked_list",
    "stack",
    "queue",
    "hash_table",
    "tree",
    "graph",
]

OPENDSA_PAGE_MAP: dict[str, str] = {
    "stack_introduction":   "Stacks",
    "stack_push":           "Stacks",
    "stack_pop":            "Stacks",
    "queue_introduction":   "Queue",
    "linked_list":          "LinkedList",
    "binary_search":        "BinarySearch",
    "sorting_bubble":       "BubbleSort",
    "sorting_merge":        "MergeSort",
    "hash_table":           "HashIntro",
    "binary_tree":          "BinaryTree",
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
