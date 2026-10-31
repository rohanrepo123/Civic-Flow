"""LangGraph workflow skeleton; nodes are deterministic and provider independent."""
from typing import TypedDict, Any

class AgentState(TypedDict, total=False):
    message: str
    context: dict[str, Any]
    intent: str
    stages: list[str]
    missing_information: list[str]
    advice: str

def _stage(name, fn):
    def node(state: AgentState):
        out = fn(state)
        return {**out, "stages": [*state.get("stages", []), name]}
    return node

def understand(state):
    text = state.get("message", "").lower()
    intent = "eligibility_question" if "eligible" in text or "eligibility" in text else "service_assistance"
    return {"intent": intent}

def discover(state): return {}
def evaluate(state): return {"missing_information": []}
def reason_documents(state): return {}
def detect_missing(state): return {}
def prepare_form(state): return {"advice": "Confirm details and documents before preparing a form."}
def explain_validation(state): return {}
def structure(state): return {}

try:
    from langgraph.graph import StateGraph, START, END
    builder = StateGraph(AgentState)
    builder.add_node("intent_understanding", _stage("intent_understanding", understand))
    builder.add_node("service_discovery", _stage("service_discovery", discover))
    builder.add_node("eligibility_evaluation", _stage("eligibility_evaluation", evaluate))
    builder.add_node("document_requirement_reasoning", _stage("document_requirement_reasoning", reason_documents))
    builder.add_node("missing_information_detection", _stage("missing_information_detection", detect_missing))
    builder.add_node("form_preparation_advice", _stage("form_preparation_advice", prepare_form))
    builder.add_node("validation_explanation", _stage("validation_explanation", explain_validation))
    builder.add_node("structured_response", _stage("structured_response", structure))
    steps = ["intent_understanding", "service_discovery", "eligibility_evaluation", "document_requirement_reasoning", "missing_information_detection", "form_preparation_advice", "validation_explanation", "structured_response"]
    builder.add_edge(START, steps[0])
    for left, right in zip(steps, steps[1:]): builder.add_edge(left, right)
    builder.add_edge(steps[-1], END)
    agent_graph = builder.compile()
except ImportError:
    # Local source checkout can still run the explicitly labelled deterministic API.
    agent_graph = None

def run_workflow(message: str, context: dict | None = None) -> AgentState:
    state: AgentState = {"message": message, "context": context or {}, "stages": []}
    if agent_graph is not None:
        return agent_graph.invoke(state)
    for name, fn in [("intent_understanding", understand), ("service_discovery", discover),
        ("eligibility_evaluation", evaluate), ("document_requirement_reasoning", reason_documents),
        ("missing_information_detection", detect_missing), ("form_preparation_advice", prepare_form),
        ("validation_explanation", explain_validation), ("structured_response", structure)]:
        state.update(fn(state)); state.setdefault("stages", []).append(name)
    return state
