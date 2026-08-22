import os

import sys
import uuid
import time
from dotenv import load_dotenv
from langgraph.types import Command
# Add project root to path to ensure clean imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.agent.graph import create_agent_graph, print_graph_ascii
from app.utils.logger import log_execution_trace

# Load env variables explicitly
workspace_env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
load_dotenv(dotenv_path=workspace_env_path, override=True)

def run_agent_workflow(app, question: str):
    """
    Runs the LangGraph agent workflow for a given user question,
    tracks the executed nodes, execution latency, and logs a structured trace.
    """
    request_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": request_id}}
    
    # Trace attributes
    visited_nodes = []
    start_time = time.time()
    
    # Initialize the input for the START state
    current_input = {"original_question": question, "retry_count": 0}
    
    while True:
        # Run stream in "updates" mode to capture node executions
        stream = app.stream(current_input, config, stream_mode="updates")
        
        # Consume the stream
        for event in stream:
            # event is a dict: { "node_name": { state_updates } }
            for node_name in event.keys():
                if node_name not in ["__metadata__", "__root__"]:
                    visited_nodes.append(node_name)
                    print(f" - [Graph Transition] Visited Node: {node_name}")
            
        # Inspect state after stream pauses or finishes
        state = app.get_state(config)
        
        # Check if the graph is paused at 'ask_clarification'
        if state.next and state.next[0] == "ask_clarification":
            question_text = state.values.get("clarification_question")
            options = state.values.get("options", [])
            
            print(f"\nAgent: {question_text}")
            for idx, opt in enumerate(options):
                print(f"  [{idx + 1}] {opt}")
            
            # Request selection from user
            user_choice = input("\nYou: ").strip()
            
            # Prepare Command(resume=...) to send response and resume
            current_input = Command(resume=user_choice)
        else:
            # Graph finished execution or hit a terminal error state
            break
            
    # Calculate execution time
    execution_time_ms = (time.time() - start_time) * 1000
    
    # Retrieve the final state values
    final_state = app.get_state(config)
    generated_sql = final_state.values.get("generated_sql")
    final_answer = final_state.values.get("final_answer")
    validation_passed = final_state.values.get("validation_result", False)
    retries = final_state.values.get("retry_count", 0)
    error = final_state.values.get("error")
    retrieved_tables = final_state.values.get("tables_used", [])
    
    # Log the execution trace (sanitized for security)
    log_execution_trace(
        request_id=request_id,
        question=question,
        visited_nodes=visited_nodes,
        retrieved_tables=retrieved_tables,
        generated_sql=generated_sql,
        validation_passed=validation_passed,
        execution_time_ms=execution_time_ms,
        retries=retries,
        error=error
    )
    
    if generated_sql:
        print(f"\nGenerated SQL:\n{generated_sql}")
        
    if final_answer:
        print(f"\nAgent:\n{final_answer}")
    elif final_state.values.get("error"):
        print(f"\nAgent: Sorry, I encountered an error: {final_state.values.get('error')}")

def main():
    print("==================================================")
    print("      QUERYPILOT: TEXT-TO-SQL AGENT WORKFLOW      ")
    print("==================================================")
    
    # 1. Print visual LangGraph layout on startup
    print_graph_ascii()
    
    app = create_agent_graph()
    print("Type 'exit' to quit.\n")
    
    while True:
        try:
            question = input("\nYou: ").strip()
            if not question:
                continue
            if question.lower() in ["exit", "quit"]:
                print("Exiting. Goodbye!")
                break
                
            run_agent_workflow(app, question)
                
        except KeyboardInterrupt:
            print("\nExiting. Goodbye!")
            break
        except Exception as e:
            print(f"\nAn error occurred: {e}")

if __name__ == "__main__":
    main()
