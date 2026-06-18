"""
Student Profile Schema  —  Kishore's Work
Defines the canonical StudentProfile dataclass used across the system.
Every field maps directly to what MonitorAgent updates and
DecisionEngine reads.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any


@dataclass
class StudentProfile:
    """
    Canonical schema for a student profile.

    Fields
    ------
    student_id      : Unique identifier  (e.g. "KISH-001")
    name            : Display name
    level           : "beginner" | "intermediate" | "advanced"
    current_topic   : Topic currently being studied (None if fresh)
    progress        : List of topics the student has mastered (score >= 0.65, engagement >= medium)
    engagement      : "low" | "medium" | "high"
    last_score      : Float 0–1 from the last quiz/interaction
    learning_history: List of {topic, score} dicts (chronological)
    frustration_level : 0–10 integer (0 = calm, 10 = very frustrated)
    engagement_score  : 0–10 integer composite engagement score
    learning_style    : "visual" | "balanced" | "problem-solver"
    last_active       : ISO-8601 datetime string of last session
    """

    student_id: str
    name: str
    level: str = "beginner"
    subject: str = "python_general"
    current_topic: Optional[str] = None
    progress: List[str] = field(default_factory=list)
    engagement: str = "medium"
    last_score: float = 0.0
    learning_history: List[dict] = field(default_factory=list)
    frustration_level: int = 0
    engagement_score: int = 5
    learning_style: str = "balanced"
    last_active: Optional[str] = None

    # --- Metrics tracking fields ---
    accuracy_history: List[float] = field(default_factory=list)
    learning_gain_history: List[float] = field(default_factory=list)
    learning_gain: float = 0.0
    normalized_learning_gain: float = 0.0
    pretest_score: Optional[float] = None
    posttest_score: Optional[float] = None
    assessment_scores: Dict[str, Dict[str, Dict[str, Any]]] = field(default_factory=dict)
    assessment_history: List[dict] = field(default_factory=list)
    knowledge_state: Dict[str, Any] = field(default_factory=lambda: {"concepts": {}, "version": 1})
    knowledge_events: List[dict] = field(default_factory=list)
    delivered_chunks: Dict[str, Dict[str, List[str]]] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Serialise to dict for JSON storage and agent consumption."""
        return {
            "student_id": self.student_id,
            "name": self.name,
            "level": self.level,
            "subject": self.subject,
            "current_topic": self.current_topic,
            "progress": self.progress,
            "engagement": self.engagement,
            "last_score": self.last_score,
            "learning_history": self.learning_history,
            "frustration_level": self.frustration_level,
            "engagement_score": self.engagement_score,
            "learning_style": self.learning_style,
            "last_active": self.last_active,
            "accuracy_history": self.accuracy_history,
            "learning_gain_history": self.learning_gain_history,
            "learning_gain": self.learning_gain,
            "normalized_learning_gain": self.normalized_learning_gain,
            "pretest_score": self.pretest_score,
            "posttest_score": self.posttest_score,
            "assessment_scores": self.assessment_scores,
            "assessment_history": self.assessment_history,
            "knowledge_state": self.knowledge_state,
            "knowledge_events": self.knowledge_events,
            "delivered_chunks": self.delivered_chunks,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "StudentProfile":
        """Deserialise from a JSON-loaded dict."""
        return cls(
            student_id=str(data.get("student_id", "UNKNOWN")),
            name=str(data.get("name", "Student")),
            level=str(data.get("knowledge_level", data.get("level", "beginner"))),
            subject=str(data.get("subject", "python_general")),
            current_topic=data.get("current_topic"),
            progress=data.get('completed_topics', data.get('progress', [])),
            engagement=str(data.get("engagement", "medium")),
            last_score=float(data.get("last_score", 0.0)),
            learning_history=data.get('learning_history', []),
            frustration_level=int(data.get("frustration_level", 0)),
            engagement_score=int(data.get("engagement_score", 5)),
            learning_style=str(data.get("learning_style", "balanced")),
            last_active=data.get("last_active"),
            accuracy_history=data.get("accuracy_history", []),
            learning_gain_history=data.get("learning_gain_history", []),
            learning_gain=float(data.get("learning_gain", 0.0)),
            normalized_learning_gain=float(data.get("normalized_learning_gain", 0.0)),
            pretest_score=data.get("pretest_score"),
            posttest_score=data.get("posttest_score"),
            assessment_scores=data.get("assessment_scores", {}),
            assessment_history=data.get("assessment_history", []),
            knowledge_state=data.get("knowledge_state", {"concepts": {}, "version": 1}),
            knowledge_events=data.get("knowledge_events", []),
            delivered_chunks=data.get("delivered_chunks", {}),
        )
