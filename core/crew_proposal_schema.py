from dataclasses import dataclass, asdict, field
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
    rag_chunk_records: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
