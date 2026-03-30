from langgraph.graph import StateGraph, END

from core.decision_engine import DecisionEngine
from core.education_crew import EducationCrew
from core.validation_agent import ValidationAgent
from core.monitor_agent import MonitorAgent
from core.file_manager_agent import FileManagerAgent
from core.student_profile_agent import StudentProfileAgent
from core.logging_utils import trace_event


# ---------------------------------------------------
# Instantiate system components
# ---------------------------------------------------

decision_engine = DecisionEngine()
education_crew = EducationCrew()
validation_agent = ValidationAgent()
monitor_agent = MonitorAgent()
file_manager_agent = FileManagerAgent()
student_profile_agent = StudentProfileAgent()


# ---------------------------------------------------
# NODE FUNCTIONS
# ---------------------------------------------------

def decision_node(state: dict):
    """
    Decision Engine Node
    Determines next step in adaptive workflow.
    """

    trace_event("node_enter", {"node": "decision"})
    decision = decision_engine.decide_next_step(
        state["student_state"]
    )

    state["decision"] = decision

    trace_event("node_exit", {"node": "decision"})
    return state


def education_crew_node(state: dict):
    """
    Education Crew Node
    Runs internal multi-agent logic.
    """

    trace_event("node_enter", {"node": "education_crew"})
    state = education_crew.run(state)
    # Ensure monitor has access to decision context
    if "crew_output" in state:
        state["crew_output"]["decision"] = state.get("decision", {})
    trace_event("node_exit", {"node": "education_crew"})
    return state


def validation_node(state: dict):
    """
    Validation Agent Node
    Ensures generated content meets rules.
    """

    trace_event("node_enter", {"node": "validation"})
    state["crew_output"] = validation_agent.validate_content(
        state["crew_output"]
    )
    trace_event("node_exit", {"node": "validation"})

    return state


def monitor_node(state: dict):
    """
    Monitor Agent Node
    Updates student state based on interaction.
    """

    trace_event("node_enter", {"node": "monitor"})
    monitor_output = monitor_agent.interact(
        state.get("crew_output", {}),
        state.get("student_state", {})
    )

    state["student_state"] = monitor_output["updated_student_state"]

    trace_event("node_exit", {"node": "monitor"})
    return state


def file_manager_node(state: dict):
    """
    File Manager Node
    Prepares RAG knowledge base before learning loop.
    """
    trace_event("node_enter", {"node": "file_manager"})
    status = file_manager_agent.prepare_knowledge_base()
    state["rag_status"] = status
    trace_event("node_exit", {"node": "file_manager"})
    return state


def profile_node(state: dict):
    """
    Student Profile Node
    Persists student state after monitoring.
    """
    trace_event("node_enter", {"node": "student_profile"})
    state["student_state"] = student_profile_agent.persist(state["student_state"])
    trace_event("node_exit", {"node": "student_profile"})
    return state


# ---------------------------------------------------
# CONDITIONAL ROUTING (ADAPTIVE FLOW)
# ---------------------------------------------------

def route_from_decision(state: dict):
    """
    Dynamic routing based on DecisionEngine output.
    """

    next_node = state["decision"]["next_node"]

    if next_node == "education_crew":
        return "education_crew"

    if next_node == "monitor_agent":
        return "monitor"

    # fallback safety
    return "education_crew"

def route_after_profile(state: dict):
    """
    Decide whether to continue learning loop
    or finish execution.
    """

    score = state["student_state"].get("last_score", 0)

    # If student not yet mastered → continue loop
    if score < 0.85:
        return "continue_learning"

    # If mastery achieved → stop
    return "end_learning"



# ---------------------------------------------------
# BUILD LANGGRAPH
# ---------------------------------------------------

builder = StateGraph(dict)

# Add nodes
builder.add_node("file_manager", file_manager_node)
builder.add_node("decision", decision_node)
builder.add_node("education_crew", education_crew_node)
builder.add_node("validation", validation_node)
builder.add_node("monitor", monitor_node)
builder.add_node("student_profile", profile_node)

# Entry point
builder.set_entry_point("file_manager")

builder.add_edge("file_manager", "decision")

# Conditional routing from decision node
builder.add_conditional_edges(
    "decision",
    route_from_decision,
    {
        "education_crew": "education_crew",
        "monitor": "monitor"
    }
)

builder.add_conditional_edges(
    "student_profile",
    route_after_profile,
    {
        "continue_learning": "decision",
        "end_learning": END
    }
)


# Remaining edges
builder.add_edge("education_crew", "validation")
builder.add_edge("validation", "monitor")
builder.add_edge("monitor", "student_profile")


# Compile graph
adaptive_graph = builder.compile()
