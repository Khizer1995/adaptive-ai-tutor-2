from langgraph.graph import StateGraph, END

from core.decision_engine import DecisionEngine
from core.education_crew import EducationCrew
from core.validation_agent import ValidationAgent
from core.monitor_agent import MonitorAgent
from core.file_manager_agent import FileManagerAgent
from core.student_profile_agent import StudentProfileAgent
from core.teacher_review_agent import TeacherReviewAgent
from core.knowledge_state_updater import apply_execution_feedback, ensure_knowledge_state
from core.logging_utils import trace_event
from core.learning_record import log_state_learning_record


decision_engine = DecisionEngine()
education_crew = EducationCrew()
validation_agent = ValidationAgent()
monitor_agent = MonitorAgent()
file_manager_agent = FileManagerAgent()
student_profile_agent = StudentProfileAgent()
teacher_review_agent = TeacherReviewAgent()


def macro_decision_node(state: dict):
    trace_event("node_enter", {"node": "macro_decision"})
    student_state = ensure_knowledge_state(state.get("student_state", {}))
    macro_decision = decision_engine.decide_macro_plan(student_state)
    state["student_state"] = student_state
    state["macro_decision"] = macro_decision
    trace_event("node_exit", {"node": "macro_decision"})
    return state


def micro_decision_node(state: dict):
    trace_event("node_enter", {"node": "micro_decision"})
    student_state = state["student_state"]
    student_state["macro_decision"] = state.get("macro_decision", {})
    decision = decision_engine.decide_next_step(student_state)
    state["decision"] = decision
    state.setdefault("decision_trace", []).append(
        {"macro_decision": state.get("macro_decision", {}), "micro_decision": decision}
    )
    trace_event("node_exit", {"node": "micro_decision"})
    return state


def education_crew_node(state: dict):
    trace_event("node_enter", {"node": "education_crew"})
    state = education_crew.run(state)
    trace_event("node_exit", {"node": "education_crew"})
    return state


def arbitration_node(state: dict):
    trace_event("node_enter", {"node": "arbitration"})
    selected = decision_engine.arbitrate_crew_proposals(
        state.get("decision", {}),
        state.get("crew_proposals", []),
        state.get("student_state", {}),
    )
    state["crew_output"] = selected
    state["arbitration_trace"] = {
        "selected_proposal": selected.get("proposal_id"),
        "selected_owner": selected.get("owner_agent"),
    }
    trace_event("node_exit", {"node": "arbitration"})
    return state


def validation_node(state: dict):
    trace_event("node_enter", {"node": "validation"})
    state["crew_output"] = validation_agent.validate_content(state.get("crew_output", {}))
    trace_event("node_exit", {"node": "validation"})
    return state


def teacher_review_node(state: dict):
    trace_event("node_enter", {"node": "teacher_review"})
    review = teacher_review_agent.review(
        state.get("crew_output", {}),
        state.get("student_state", {}),
    )
    state["teacher_review"] = review
    if review.get("review_status") == "approved":
        log_state_learning_record(state)
    trace_event("node_exit", {"node": "teacher_review"})
    return state


def teacher_review_node(state: dict):
    """
    Teacher Review Node
    Uses JSON review queue to approve/reject content.
    """
    trace_event("node_enter", {"node": "teacher_review"})
    review = teacher_review_agent.review(
        state.get("crew_output", {}),
        state.get("student_state", {})
    )
    state["teacher_review"] = review
    if review.get("review_status") == "approved":
        log_state_learning_record(state)
    trace_event("node_exit", {"node": "teacher_review"})
    return state


def monitor_node(state: dict):
    trace_event("node_enter", {"node": "monitor"})
    monitor_output = monitor_agent.interact(
        state.get("crew_output", {}),
        state.get("student_state", {}),
    )
    state["student_state"] = monitor_output["updated_student_state"]
    state["execution_feedback"] = monitor_output.get("execution_feedback", {})
    trace_event("node_exit", {"node": "monitor"})
    return state


def knowledge_state_node(state: dict):
    trace_event("node_enter", {"node": "knowledge_state"})
    state["student_state"] = apply_execution_feedback(
        state.get("student_state", {}),
        state.get("execution_feedback", {}),
        state.get("macro_decision", {}),
    )
    trace_event("node_exit", {"node": "knowledge_state"})
    return state


def file_manager_node(state: dict):
    trace_event("node_enter", {"node": "file_manager"})
    status = file_manager_agent.prepare_knowledge_base()
    state["rag_status"] = status
    trace_event("node_exit", {"node": "file_manager"})
    return state


def profile_node(state: dict):
    trace_event("node_enter", {"node": "student_profile"})
    state["student_state"] = student_profile_agent.persist(state["student_state"])
    trace_event("node_exit", {"node": "student_profile"})
    return state


def route_from_micro_decision(state: dict):
    next_node = state["decision"]["next_node"]
    if next_node == "education_crew":
        return "education_crew"
    if next_node == "monitor_agent":
        return "monitor"
    return "education_crew"


def route_after_profile(state: dict):
    score = state["student_state"].get("last_score", 0)
    if score < 0.85:
        return "continue_learning"
    return "end_learning"


def route_after_teacher_review(state: dict):
    review = state.get("teacher_review", {})
    status = review.get("review_status", "pending")
    if status == "approved":
        return "approved"
    return "halt"


builder = StateGraph(dict)
builder.add_node("file_manager", file_manager_node)
builder.add_node("macro_decision", macro_decision_node)
builder.add_node("micro_decision", micro_decision_node)
builder.add_node("education_crew", education_crew_node)
builder.add_node("arbitration", arbitration_node)
builder.add_node("validation", validation_node)
builder.add_node("teacher_review", teacher_review_node)
builder.add_node("monitor", monitor_node)
builder.add_node("knowledge_state", knowledge_state_node)
builder.add_node("student_profile", profile_node)

builder.set_entry_point("file_manager")
builder.add_edge("file_manager", "macro_decision")
builder.add_edge("macro_decision", "micro_decision")

builder.add_conditional_edges(
    "micro_decision",
    route_from_micro_decision,
    {"education_crew": "education_crew", "monitor": "monitor"},
)

builder.add_edge("education_crew", "arbitration")
builder.add_edge("arbitration", "validation")
builder.add_edge("validation", "teacher_review")

builder.add_conditional_edges(
    "teacher_review",
    route_after_teacher_review,
    {"approved": "monitor", "halt": END},
)

builder.add_edge("monitor", "knowledge_state")
builder.add_edge("knowledge_state", "student_profile")

builder.add_conditional_edges(
    "teacher_review",
    route_after_teacher_review,
    {
        "approved": "monitor",
        "halt": END
    }
)

builder.add_conditional_edges(
    "student_profile",
    route_after_profile,
    {"continue_learning": "macro_decision", "end_learning": END},
)

adaptive_graph = builder.compile()
