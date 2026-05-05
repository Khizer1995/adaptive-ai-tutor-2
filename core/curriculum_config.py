from __future__ import annotations

UNLOCK_THRESHOLD = 0.70

TOPIC_SUBTOPICS: dict[str, list[dict[str, str]]] = {
    "stack": [
        {"id": "stack_introduction", "title": "Introduction & Concept"},
        {"id": "stack_push", "title": "Push Operation"},
        {"id": "stack_pop", "title": "Pop Operation"},
        {"id": "stack_peek", "title": "Peek Operation"},
        {"id": "stack_isempty_isfull", "title": "isEmpty / isFull"},
        {"id": "stack_array", "title": "Stack using Array"},
        {"id": "stack_linked_list", "title": "Stack using Linked List"},
        {"id": "stack_applications", "title": "Applications (expression evaluation, backtracking)"},
    ]
}

OPENDSA_PAGE_MAP: dict[str, str] = {
    "stack_introduction": "Stacks",
    "stack_push": "Stacks",
    "stack_pop": "Stacks",
    "queue_introduction": "Queue",
    "linked_list": "LinkedList",
    "binary_search": "BinarySearch",
    "sorting_bubble": "BubbleSort",
    "sorting_merge": "MergeSort",
    "hash_table": "HashIntro",
    "binary_tree": "BinaryTree",
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
