from dataclasses import dataclass, asdict
from typing import Any, Dict, List


@dataclass
class CrewProposal:
    proposal_id: str
    owner_agent: str
    learning_path: str
    quiz: List[str]
    teacher_style: str
    rag_chunks: List[str]
    engineered_query: str
    confidence: float
    challenge_level: str
    execution_cost: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
