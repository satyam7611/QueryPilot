from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from app.agent.state import AgentState
from app.agent.nodes.analyze import analyze_question
from app.agent.nodes.clarify import ask_clarification, merge_clarification
from app.agent.nodes.retrieve_schema import retrieve_schema
from app.agent.nodes.generate_sql import generate_sql
from app.agent.nodes.validate_sql import validate_sql
from app.agent.nodes.execute_sql import execute_sql
from app.agent.nodes.answer import generate_answer
from app.agent.nodes.error import handle_out_of_domain

# 1. Define Conditional Routing Functions

def route_after_analysis(state: AgentState) -> str:
    """
    Decides the path to take based on the initial analysis of the question.
    """
    if state.get("is_out_of_domain"):
        return "out_of_domain"
    elif state.get("is_ambiguous"):
        return "ambiguous"
    else:
        return "clear"

def route_after_validation(state: AgentState) -> str:
    """
    Decides if the query is safe/valid or if it should be regenerated.
    """
    if state.get("validation_result"):
        return "execute"
    
    # If invalid, check retry limits
    retries = state.get("retry_count", 0)
    if retries < 2:
        print(f" - Validation failed. Retrying... (Attempt {retries + 1}/2)")
        return "retry"
    else:
        print(" - Validation failed. Max retries exceeded.")
        return "fail"

# 2. Build the State Graph

def create_agent_graph():
    # Initialize StateGraph with our custom AgentState
    workflow = StateGraph(AgentState)
    
    # Register Nodes
    workflow.add_node("analyze_question", analyze_question)
    workflow.add_node("ask_clarification", ask_clarification)
    workflow.add_node("merge_clarification", merge_clarification)
    workflow.add_node("handle_out_of_domain", handle_out_of_domain)
    workflow.add_node("retrieve_schema", retrieve_schema)
    workflow.add_node("generate_sql", generate_sql)
    workflow.add_node("validate_sql", validate_sql)
    workflow.add_node("execute_sql", execute_sql)
    workflow.add_node("generate_answer", generate_answer)
    
    # Define Edges & Routing Rules
    workflow.set_entry_point("analyze_question")
    
    # Route from analyze_question
    workflow.add_conditional_edges(
        "analyze_question",
        route_after_analysis,
        {
            "out_of_domain": "handle_out_of_domain",
            "ambiguous": "ask_clarification",
            "clear": "retrieve_schema"
        }
    )
    
    # Clarification Branch
    workflow.add_edge("ask_clarification", "merge_clarification")
    workflow.add_edge("merge_clarification", "retrieve_schema")
    
    # Out of Domain terminates directly
    workflow.add_edge("handle_out_of_domain", END)
    
    # Database flow
    workflow.add_edge("retrieve_schema", "generate_sql")
    workflow.add_edge("generate_sql", "validate_sql")
    
    # Route after validation (Self-correction loop)
    workflow.add_conditional_edges(
        "validate_sql",
        route_after_validation,
        {
            "execute": "execute_sql",
            "retry": "generate_sql",
            "fail": "generate_answer"
        }
    )
    
    # Execute to Answer
    workflow.add_edge("execute_sql", "generate_answer")
    workflow.add_edge("generate_answer", END)
    
    # Initialize Memory Saver to act as checkpointer (retains thread state across turns)
    memory = MemorySaver()
    
    # Compile the graph
    return workflow.compile(checkpointer=memory)

# 3. Graph Visualizer
def print_graph_ascii():
    """Prints the graph visual layout directly to the terminal."""
    try:
        app = create_agent_graph()
        print("\n" + "=" * 50)
        print("            LANGGRAPH WORKFLOW LAYOUT             ")
        print("=" * 50)
        app.get_graph().print_ascii()
        print("=" * 50 + "\n")
    except Exception as e:
        print(f"Could not print ASCII graph layout: {e}")
