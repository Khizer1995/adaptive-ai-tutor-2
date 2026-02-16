from langgraph.graph import StateGraph, END

from core.decision_engine import DecisionEngine
from core.education_crew import EducationCrew
from core.validation_agent import ValidationAgent
from core.monitor_agent import MonitorAgent


# ---------------------------------------------------
# Instantiate system components
# ---------------------------------------------------

decision_engine = DecisionEngine()
education_crew = EducationCrew()
validation_agent = ValidationAgent()
monitor_agent = MonitorAgent()


# ---------------------------------------------------
# NODE FUNCTIONS
# ---------------------------------------------------

def decision_node(state: dict):
    """
    Decision Engine Node
    Determines next step in adaptive workflow.
    """

    decision = decision_engine.decide_next_step(
        state["student_state"]
    )

    state["decision"] = decision

    return state


def education_crew_node(state: dict):
    """
    Education Crew Node
    Runs internal multi-agent logic.
    """

    return education_crew.run(state)


def validation_node(state: dict):
    """
    Validation Agent Node
    Ensures generated content meets rules.
    """

    state["crew_output"] = validation_agent.validate_content(
        state["crew_output"]
    )

    return state


def monitor_node(state: dict):
    """
    Monitor Agent Node
    Updates student state based on interaction.
    """

    monitor_output = monitor_agent.interact(
        state["crew_output"],
        state["student_state"]
    )

    state["student_state"] = monitor_output["updated_student_state"]

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

def route_after_monitor(state: dict):
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
builder.add_node("decision", decision_node)
builder.add_node("education_crew", education_crew_node)
builder.add_node("validation", validation_node)
builder.add_node("monitor", monitor_node)

# Entry point
builder.set_entry_point("decision")

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
    "monitor",
    route_after_monitor,
    {
        "continue_learning": "decision",
        "end_learning": END
    }
)


# Remaining edges
builder.add_edge("education_crew", "validation")
builder.add_edge("validation", "monitor")


# Compile graph
adaptive_graph = builder.compile()
