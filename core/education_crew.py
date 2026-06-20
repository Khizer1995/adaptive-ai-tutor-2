"""
education_crew.py
=================
Root-cause fix for Issue #4:
  Previously, _build_competing_proposals() called
  self.practical.generate_quiz_batch() during content generation, which caused
  quiz content to appear alongside learning content.

  Now, proposals carry ONLY the learning path.  Quiz generation is invoked
  exclusively from the /quiz/generate endpoint (on-demand), keeping the two
  phases completely separate.
"""

from core.tutor_agent import TutorAgent
from core.practical_agent import PracticalAgent
from core.teacher_persona_agent import TeacherPersonaAgent
from core.crew_proposal_schema import CrewProposal
from core.logging_utils import get_logger, trace_event, Timer


class EducationCrew:
    """
    Adaptive Education Crew

    Produces competing proposals from crew members.
    Selection is handled by the LangGraph decision layer.

    KEY CHANGE: Proposals no longer include quiz questions.
    Quiz generation is a separate on-demand operation.
    """

    def __init__(self):
        self.tutor = TutorAgent()
        self.practical = PracticalAgent()
        self.persona = TeacherPersonaAgent()
        self.logger = get_logger("education_crew", "crew.log")

    def execute(self, decision_output: dict, student_state: dict):
        state = {
            "decision": decision_output,
            "student_state": student_state,
        }
        state = self.run(state)
        return state["crew_output"]

    def run(self, state: dict):
        timer = Timer()
        decision = state["decision"]
        student_state = state["student_state"]
        action = decision.get("action", "default")

        proposals = self._build_competing_proposals(decision, student_state)
        state["crew_proposals"] = proposals
        state["crew_output"] = proposals[0] if proposals else {"decision": decision}

        duration_ms = round(timer.elapsed_ms(), 2)
        self.logger.info(
            f"action={action} topic='{student_state.get('current_topic')}' "
            f"proposals={len(proposals)} duration_ms={duration_ms}"
        )
        trace_event(
            "crew_completed",
            {
                "action": action,
                "topic": student_state.get("current_topic"),
                "proposals": len(proposals),
                "duration_ms": duration_ms,
            },
        )
        return state

    def _build_competing_proposals(self, decision: dict, student_state: dict) -> list[dict]:
        if decision.get("action") == "advance_topic":
            student_state["current_topic"] = None

        base_learning = self._extract_learning(
            self.tutor.generate_learning_path(decision, student_state)
        )
        teacher_style = self.persona.apply_persona(student_state)
        action = decision.get("action", "default")

        if action in ("increase_support", "reinforce_basics"):
            tutor_challenge = "low"
            practical_challenge = "low"
        elif action in ("increase_challenge", "challenge_with_variation", "advance_topic"):
            tutor_challenge = "high"
            practical_challenge = "high"
        else:
            tutor_challenge = "medium"
            practical_challenge = "medium"

        # Get RAG timing from base_learning
        rag_latency_ms = base_learning.get("rag_latency_ms", 0.0)
        
        # ── FIX #4: NO quiz generation here — empty quiz lists in proposals ──
        proposals = [
            CrewProposal(
                proposal_id="tutor_plan",
                owner_agent="tutor_agent",
                learning_path=base_learning.get("learning_path", ""),
                quiz=[],          # EMPTY — quiz is on-demand only
                teacher_style=teacher_style,
                rag_chunks=base_learning.get("rag_chunks", []),
                engineered_query=base_learning.get("engineered_query", ""),
                confidence=0.78,
                challenge_level=tutor_challenge,
                execution_cost=0.55,
                rag_chunk_records=base_learning.get("rag_chunk_records", []),
            ).to_dict(),
            CrewProposal(
                proposal_id="practice_plan",
                owner_agent="practical_agent",
                learning_path=base_learning.get("learning_path", ""),
                quiz=[],          # EMPTY — quiz is on-demand only
                teacher_style=teacher_style,
                rag_chunks=base_learning.get("rag_chunks", []),
                engineered_query=base_learning.get("engineered_query", ""),
                confidence=0.74,
                challenge_level=practical_challenge,
                execution_cost=0.7,
                rag_chunk_records=base_learning.get("rag_chunk_records", []),
            ).to_dict(),
            CrewProposal(
                proposal_id="persona_plan",
                owner_agent="teacher_persona",
                learning_path=base_learning.get("learning_path", ""),
                quiz=[],          # EMPTY — quiz is on-demand only
                teacher_style=teacher_style,
                rag_chunks=base_learning.get("rag_chunks", []),
                engineered_query=base_learning.get("engineered_query", ""),
                confidence=0.7,
                challenge_level="medium",
                execution_cost=0.45,
                rag_chunk_records=base_learning.get("rag_chunk_records", []),
            ).to_dict(),
        ]

        # Add RAG latency and decision to all proposals
        for proposal in proposals:
            proposal["decision"] = decision
            proposal["rag_latency_ms"] = rag_latency_ms  # Add RAG timing to each proposal
        trace_event(
            "crew_proposals_generated",
            {"proposal_ids": [p["proposal_id"] for p in proposals], "action": action},
        )
        return proposals

    def _extract_learning(self, learning_path_result):
        if isinstance(learning_path_result, dict):
            return {
                "learning_path": learning_path_result.get("llm_synthesis"),
                "rag_chunks": learning_path_result.get("rag_chunks", []),
                "rag_chunk_records": learning_path_result.get("rag_chunk_records", []),
                "engineered_query": learning_path_result.get("engineered_query", ""),
                "adaptive_ctx": learning_path_result.get("adaptive_ctx", {}),
                "rag_latency_ms": learning_path_result.get("rag_latency_ms", 0.0),  # Pass RAG timing
            }
        return {"learning_path": learning_path_result}
