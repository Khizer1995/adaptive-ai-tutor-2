from __future__ import annotations

import re
from typing import Dict, List, Tuple


TOPIC_KEYWORDS: Dict[str, List[str]] = {
    "array": ["array", "list indexing", "dynamic array", "searching", "sorting"],
    "queue": ["queue", "enqueue", "dequeue", "fifo", "circular", "priority", "deque"],
    "graph": ["graph", "bfs", "dfs", "adjacency", "shortest path", "topological"],
}

CONCEPT_PATTERNS: List[Tuple[str, List[str]]] = [
    ("definition", ["what is", "definition", "overview", "introduction"]),
    ("operations", ["operation", "push", "pop", "insert", "delete", "search"]),
    ("implementation", ["implementation", "code", "python", "algorithm"]),
    ("applications", ["application", "use case", "real world"]),
    ("collision_handling", ["collision", "chaining", "open addressing", "probing"]),
    ("complexity", ["time complexity", "space complexity", "big-o"]),
    ("edge_cases", ["edge case", "boundary", "overflow", "underflow"]),
]

EXAMPLE_HINTS = ["example", "illustration", "walkthrough", "trace"]


def normalize_topic(text: str, default: str = "general_dsa") -> str:
    lowered = text.lower()
    for topic, keys in TOPIC_KEYWORDS.items():
        if any(key in lowered for key in keys):
            return topic
    return default


def infer_concept(text: str, fallback: str = "core_concept") -> str:
    lowered = text.lower()
    for concept, keys in CONCEPT_PATTERNS:
        if any(key in lowered for key in keys):
            return concept
    return fallback


def infer_difficulty(text: str, source: str) -> str:
    lowered = text.lower()
    if source == "opendsa":
        if any(k in lowered for k in ["proof", "amortized", "optimal", "invariant"]):
            return "intermediate"
        return "beginner"
    if any(k in lowered for k in ["advanced", "optimization", "amortized", "tradeoff"]):
        return "advanced"
    if any(k in lowered for k in ["implementation", "code", "complexity", "collision"]):
        return "intermediate"
    return "beginner"


def infer_content_type(title: str, content: str) -> str:
    lowered = f"{title} {content}".lower()
    if any(h in lowered for h in EXAMPLE_HINTS):
        return "example"
    if any(k in lowered for k in ["implementation", "code", "python", "pseudocode"]):
        return "implementation"
    return "concept"


def sanitize_text(text: str) -> str:
    text = re.sub(r"\r", "\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def concept_key(title: str, body: str) -> str:
    c = infer_concept(f"{title}\n{body}")
    return c

