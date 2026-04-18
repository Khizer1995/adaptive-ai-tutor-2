from __future__ import annotations

from typing import List


SECTION_HEADERS: List[str] = [
    "Concept Overview",
    "Key Points",
    "Operations/Steps",
    "Example",
    "Common Mistakes",
    "Quick Recap",
]


def build_structured_explain_query(topic: str, level: str, style: str, domain_label: str) -> str:
    return (
        f"Explain {domain_label} topic '{topic}' for a {level} learner with learning style '{style}'. "
        "Follow this exact scannable structure with no extra headings and no long prose paragraphs:\n"
        "• Concept Overview: 1-2 lines\n"
        "• Key Points: 3-5 bullets\n"
        "• Operations/Steps: numbered list if sequential, otherwise short bullets\n"
        "• Example: one minimal concrete example\n"
        "• Common Mistakes: 2-3 bullets\n"
        "• Quick Recap: 1 line\n"
        "Hard rules: do not use any legacy explanation heading and avoid long paragraphs."
    )
