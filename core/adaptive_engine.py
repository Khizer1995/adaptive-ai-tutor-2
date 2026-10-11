"""
adaptive_engine.py
==================
Central adaptive engine.  Every content-generation call should pass through
`build_content_context` so the LLM prompt is fully aware of the learner's
current performance.

Root causes fixed:
  1. Quiz score was recorded in the state but NEVER fed back into the
     generate_learning_path prompt — explanations were static.
  2. No anti-repetition guard on the generated text — same prompt produced
     the same output every time.
  3. Topic list was only one item because curriculum_config.py only defines
     "stack".  We now expose ALL topics from the layered knowledge base.
"""

from __future__ import annotations

import random
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from core.adaptive_learning import (
    adaptive_profile,
    canonical_topic,
    clamp_score,
    ensure_learning_state,
    previous_content_context,
    record_generated_content,
    record_quiz_attempt,
    stable_hash,
)


# ──────────────────────────────────────────────────────────────────────────────
# Public helpers used by TutorAgent.generate_learning_path
# ──────────────────────────────────────────────────────────────────────────────

def build_content_context(
    student_state: Dict[str, Any],
    topic: str,
    subtopic: str,
) -> Dict[str, Any]:
    """
    Build a rich context dict that the LLM prompt builder should consume.
    This is the primary fix for Issue #1 (adaptive learning not working).
    """
    ensure_learning_state(student_state)
    profile = adaptive_profile(student_state, topic)
    prior = previous_content_context(student_state, topic, subtopic)

    mode     = profile["mode"]          # "remedial" | "guided" | "advanced"
    depth    = profile["depth"]         # "beginner" | "intermediate" | "advanced"
    score    = profile["last_topic_score"]
    mastery  = profile["mastery"]
    reqs     = profile["requirements"]
    weak     = profile["weak_areas"]
    strong   = profile["strong_areas"]

    # Anti-repetition seed — changes every call so the LLM is forced to vary.
    variation_seed = stable_hash(
        f"{topic}|{subtopic}|{datetime.now(timezone.utc).strftime('%Y%m%d%H%M')}"
        f"|{score}|{random.random()}"
    )[:12]

    return {
        "mode": mode,
        "depth": depth,
        "score": score,
        "mastery": mastery,
        "requirements": reqs,
        "weak_areas": weak,
        "strong_areas": strong,
        "prior_content_summary": prior,
        "variation_seed": variation_seed,
    }


def build_adaptive_prompt(
    topic: str,
    subtopic: str,
    ctx: Dict[str, Any],
    domain_label: str,
) -> str:
    """
    Construct a fully adaptive LLM prompt from the context built above.
    This single function is responsible for ALL adaptive behaviour in content
    generation (Issue #1 + Issue #2).
    """
    mode    = ctx["mode"]
    depth   = ctx["depth"]
    score   = ctx["score"]
    mastery = ctx["mastery"]
    reqs    = ctx["requirements"]
    weak    = ctx["weak_areas"]
    strong  = ctx["strong_areas"]
    prior   = ctx["prior_content_summary"]
    seed    = ctx["variation_seed"]

    req_block = "\n".join(f"  • {r}" for r in reqs)
    weak_block = ", ".join(weak) if weak else "none identified"
    strong_block = ", ".join(strong) if strong else "none identified"

    # Mode-specific headline instruction.
    if mode == "remedial":
        headline = (
            f"The student scored {round(score * 100)}% (low).  "
            "SIMPLIFY — use beginner-friendly language, add analogies and "
            "real-world examples, break the concept into smaller chunks, and "
            "include prerequisite ideas before the main concept."
        )
    elif mode == "advanced":
        headline = (
            f"The student scored {round(score * 100)}% (high, mastery {round(mastery * 100)}%).  "
            "CHALLENGE — increase technical depth, add edge cases, compare "
            "trade-offs, and include at least one interview-style question."
        )
    else:
        headline = (
            f"The student scored {round(score * 100)}% (guided band).  "
            "Maintain steady progression: one clear explanation, one fresh "
            "example, and a self-check question."
        )

    return (
        f"[Variation seed: {seed}]\n\n"
        f"You are an adaptive {domain_label} tutor.  {headline}\n\n"
        f"Topic: {topic}\n"
        f"Subtopic: {subtopic}\n"
        f"Depth level: {depth}\n"
        f"Student weak areas: {weak_block}\n"
        f"Student strong areas: {strong_block}\n\n"
        f"Adaptive requirements (follow ALL of these):\n{req_block}\n\n"
        f"Previously generated content for this subtopic (DO NOT REPEAT):\n"
        f"{prior}\n\n"
        "Output format (strict markdown, no extra headings):\n"
        "## {topic} — {subtopic}\n\n"
        "**Overview** (1-2 sentences adapted to the student's level)\n\n"
        "**Key Points** (3-5 bullets)\n\n"
        "**How It Works** (numbered steps or short paragraphs)\n\n"
        "**Example** (one concrete code block if applicable)\n\n"
        "**Common Mistakes** (2-3 bullets)\n\n"
        "**Quick Recap** (1 sentence)\n\n"
        "Hard rules:\n"
        "  • Vary phrasing, examples, and analogies from prior content.\n"
        "  • Do NOT copy or slightly rephrase previous explanations.\n"
        "  • Match depth to the student's performance level.\n"
    )


def build_adaptive_quiz_prompt(
    topic: str,
    subtopic: str,
    ctx: Dict[str, Any],
    rag_context: str,
    q_count: int,
    seen_question_previews: List[str],
) -> str:
    """
    Build a fully adaptive quiz prompt grounded in OpenDSA/textbook source material.
    Every question must be derived from specific facts in the RAG context, not generic
    knowledge — this ensures questions are unique and drawn from the actual curriculum.
    """
    mode  = ctx["mode"]
    depth = ctx["depth"]
    score = ctx["score"]
    seed  = ctx["variation_seed"]

    seen_block = (
        "\n".join(f"  - {q}" for q in seen_question_previews[:10])
        if seen_question_previews
        else "  (none yet)"
    )

    if mode == "remedial":
        difficulty_note = (
            "Focus on foundational definitional and comprehension questions. "
            "Avoid trick questions. Use simple, unambiguous language."
        )
        types = "definitional (2), true/false (1), application (2), fill-in-blank (1)"
    elif mode == "advanced":
        difficulty_note = (
            "Include scenario-based, code-tracing, and edge-case questions. "
            "At least one question should resemble an interview prompt."
        )
        types = "scenario (2), code/output-trace (2), edge-case (1), complexity comparison (1)"
    else:
        difficulty_note = "Mix of definitional, application, and output-tracing questions."
        types = "definitional (2), application (2), code-trace (1), edge-case (1)"

    return (
        f"[Variation seed: {seed}]\n\n"
        f"You are generating quiz questions for a DSA/programming course.\n"
        f"Topic: {topic}  |  Subtopic: {subtopic}  |  Mode: {mode}  |  Depth: {depth}\n"
        f"Student last score: {round(score * 100)}%\n\n"
        "══════════════════════════════════════════\n"
        "TEXTBOOK / OpenDSA SOURCE MATERIAL\n"
        "(All questions MUST be derived from THIS content)\n"
        "══════════════════════════════════════════\n"
        f"{rag_context}\n"
        "══════════════════════════════════════════\n\n"
        f"Difficulty: {difficulty_note}\n"
        f"Question types to include: {types}\n\n"
        f"Questions already asked — DO NOT REPEAT OR REPHRASE ANY OF THESE:\n{seen_block}\n\n"
        f"Generate EXACTLY {q_count} MCQ questions. MANDATORY rules:\n"
        "  1. SOURCE GROUNDING: Every question must be derived from a specific fact,\n"
        "     definition, algorithm step, code example, complexity value, or edge-case\n"
        "     that is EXPLICITLY present in the source material above.\n"
        "     Do NOT generate questions from general knowledge — each must trace\n"
        "     back to something stated in the source.\n"
        "  2. UNIQUENESS: Each question tests a DIFFERENT concept, operation, or aspect\n"
        "     from every other question in this batch.\n"
        "  3. DISTRACTORS: Wrong options must be plausible — things a student might\n"
        "     genuinely confuse with the correct answer, not obviously absurd choices.\n"
        "  4. EXPLANATION: Each explanation must cite WHY the correct answer is right,\n"
        "     referencing the specific fact from the source material.\n"
        "  5. ANSWER POSITION: Distribute the correct answer across all 4 positions.\n"
        "     Never place it at position 0 (first option) more than once per batch.\n\n"
        "Return ONLY a valid JSON array with no extra text. Each element:\n"
        "{\n"
        '  "question": "<question text — may include short code snippet if helpful>",\n'
        '  "options": ["<opt A>", "<opt B>", "<opt C>", "<opt D>"],\n'
        '  "correct_answer": "<must exactly match one of the options>",\n'
        '  "explanation": "<1-2 sentences citing the specific fact from source>"\n'
        "}\n"
    )


def after_quiz_submit(
    student_state: Dict[str, Any],
    topic: str,
    subtopic: str,
    score: float,
    answers: List[Any],
) -> Dict[str, Any]:
    """
    Unified post-quiz handler. Calls record_quiz_attempt from adaptive_learning
    so mastery, scaffold_level, weak_areas, and level are all updated.
    This is the fix for Issue #7 (persistent learner state).
    """
    return record_quiz_attempt(student_state, topic, subtopic, score, answers)


def record_content(
    student_state: Dict[str, Any],
    topic: str,
    subtopic: str,
    content: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Thin wrapper so the API server can record content without importing
    adaptive_learning directly.
    """
    record_generated_content(student_state, topic, subtopic, content, metadata)


# ──────────────────────────────────────────────────────────────────────────────
# All-topics loader (fixes Issue #5)
# ──────────────────────────────────────────────────────────────────────────────

_DSA_TOPICS_DEFAULT = [
    {"name": "array", "order_index": 0, "subtopics": ["array_introduction", "array_operations", "array_searching", "array_sorting", "array_multidimensional", "array_applications"]},
    {"name": "queue", "order_index": 1, "subtopics": ["queue_introduction", "queue_enqueue", "queue_dequeue", "queue_circular", "queue_priority", "queue_deque", "queue_applications"]},
    {"name": "graph", "order_index": 2, "subtopics": ["graph_introduction", "graph_representation", "graph_bfs", "graph_dfs", "graph_shortest_path", "graph_topological", "graph_applications"]},
]

_PYTHON_TOPICS_DEFAULT = [
    {"name": "python_variables",  "order_index": 0,  "subtopics": ["variables_introduction", "data_types", "type_conversion"]},
    {"name": "control_flow",      "order_index": 1,  "subtopics": ["if_else", "nested_conditions", "ternary"]},
    {"name": "loops",             "order_index": 2,  "subtopics": ["for_loop", "while_loop", "loop_control"]},
    {"name": "functions",         "order_index": 3,  "subtopics": ["function_definition", "parameters", "return_values", "scope"]},
    {"name": "lists_arrays",      "order_index": 4,  "subtopics": ["list_basics", "list_methods", "list_comprehension"]},
    {"name": "oop",               "order_index": 5,  "subtopics": ["classes", "objects", "inheritance", "polymorphism"]},
    {"name": "error_handling",    "order_index": 6,  "subtopics": ["try_except", "raising_exceptions", "custom_exceptions"]},
]


def get_all_topics(subject: str = "dsa") -> List[Dict[str, Any]]:
    """
    Return the full topic list for the given subject.  First attempts to load
    from the processed knowledge base; falls back to the built-in defaults.
    """
    from core.adaptive_learning import load_source_topics

    try:
        loaded = load_source_topics()
        if loaded:
            return loaded
    except Exception:
        pass

    if "dsa" in subject.lower():
        return _DSA_TOPICS_DEFAULT
    return _PYTHON_TOPICS_DEFAULT


def get_all_subtopics_for_topic(topic: str, subject: str = "dsa") -> List[str]:
    """Return subtopic ids for a given topic."""
    # First check curriculum_config which has the definitive subtopic list for known topics.
    try:
        from core.curriculum_config import TOPIC_SUBTOPICS
        if topic in TOPIC_SUBTOPICS:
            return [item["id"] for item in TOPIC_SUBTOPICS[topic]]
    except Exception:
        pass

    # Fall back to built-in defaults.
    all_topics = get_all_topics(subject)
    for t in all_topics:
        if canonical_topic(t["name"]) == canonical_topic(topic):
            subs = t.get("subtopics", [])
            if subs:
                return subs
    return [f"{canonical_topic(topic)}_introduction"]
