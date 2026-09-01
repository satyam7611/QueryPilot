import os
import uuid
import time
from typing import Dict, Any, Optional
from langgraph.types import Command

from app.agent.graph import create_agent_graph
from app.utils.logger import log_execution_trace

# Instantiate the compiled graph once globally
_graph = None

def get_graph():
    global _graph
    if _graph is None:
        _graph = create_agent_graph()
    return _graph

def execute_query(
    question: str,
    dataset_id: Optional[str] = None,
    api_key: Optional[str] = None,
    thread_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Submits a query to the LangGraph Text-to-SQL workflow.
    Handles RAG context, API key routing, and paused clarification interrupts.
    """
    app = get_graph()
    
    # Use existing thread_id or generate a new one
    active_thread = thread_id or str(uuid.uuid4())
    config = {"configurable": {"thread_id": active_thread, "api_key": api_key}}
    
    # Tracing variables
    visited_nodes = []
    start_time = time.time()
    
    # Initialize state values, resetting all transient execution fields to prevent leakage
    initial_state = {
        "original_question": question,
        "dataset_id": dataset_id,
        "retry_count": 0,
        "is_ambiguous": False,
        "is_out_of_domain": False,
        "clarification_question": None,
        "options": None,
        "clarification_response": None,
        "clarified_intent": None,
        "retrieved_schema": None,
        "generated_sql": None,
        "explanation": None,
        "tables_used": None,
        "validation_result": None,
        "query_result": None,
        "error": None,
        "final_answer": None
    }
    
    try:
        # Run graph execution stream
        stream = app.stream(initial_state, config, stream_mode="updates")
        for event in stream:
            for node_name in event.keys():
                if node_name not in ["__metadata__", "__root__"]:
                    visited_nodes.append(node_name)
                    
        # Inspect state after execution pauses or finishes
        state = app.get_state(config)
        
        # Check if the graph is paused at 'ask_clarification' (Interrupt)
        if state.next and state.next[0] == "ask_clarification":
            return {
                "status": "clarification_required",
                "thread_id": active_thread,
                "question": state.values.get("clarification_question"),
                "options": state.values.get("options", [])
            }
            
        # Graph finished execution successfully or hit an error node
        execution_time_ms = (time.time() - start_time) * 1000
        generated_sql = state.values.get("generated_sql")
        final_answer = state.values.get("final_answer")
        validation_passed = state.values.get("validation_result", False)
        retries = state.values.get("retry_count", 0)
        error = state.values.get("error")
        retrieved_tables = state.values.get("tables_used", [])
        
        # Log sanitized telemetry trace locally
        log_execution_trace(
            request_id=active_thread,
            question=question,
            visited_nodes=visited_nodes,
            retrieved_tables=retrieved_tables,
            generated_sql=generated_sql,
            validation_passed=validation_passed,
            execution_time_ms=execution_time_ms,
            retries=retries,
            error=error,
            model="gemini-3.5-flash"
        )
        
        return {
            "status": "completed",
            "thread_id": active_thread,
            "generated_sql": generated_sql,
            "final_answer": final_answer,
            "query_result": state.values.get("query_result"),
            "validation_passed": validation_passed,
            "error": error
        }
        
    except Exception as e:
        execution_time_ms = (time.time() - start_time) * 1000
        print(f"[QueryService Error] Execution failed: {e}")
        # Log failure
        log_execution_trace(
            request_id=active_thread,
            question=question,
            visited_nodes=visited_nodes,
            retrieved_tables=[],
            generated_sql=None,
            validation_passed=False,
            execution_time_ms=execution_time_ms,
            retries=0,
            error=str(e),
            model="gemini-3.5-flash"
        )
        return {
            "status": "failed",
            "thread_id": active_thread,
            "error": f"Internal execution failure: {str(e)}"
        }

def resume_clarification(
    thread_id: str,
    choice: str,
    api_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Resumes a paused LangGraph clarification thread with the user's choice.
    """
    app = get_graph()
    config = {"configurable": {"thread_id": thread_id, "api_key": api_key}}
    
    # Retrieve current thread state to log original details
    pre_state = app.get_state(config)
    original_question = pre_state.values.get("original_question", "Resume clarification query")
    dataset_id = pre_state.values.get("dataset_id")
    
    visited_nodes = ["ask_clarification"]
    start_time = time.time()
    
    try:
        # Resume thread execution by passing Command(resume=choice)
        stream = app.stream(Command(resume=choice), config, stream_mode="updates")
        for event in stream:
            for node_name in event.keys():
                if node_name not in ["__metadata__", "__root__"]:
                    visited_nodes.append(node_name)
                    
        # Inspect state after resuming
        state = app.get_state(config)
        
        execution_time_ms = (time.time() - start_time) * 1000
        generated_sql = state.values.get("generated_sql")
        final_answer = state.values.get("final_answer")
        validation_passed = state.values.get("validation_result", False)
        retries = state.values.get("retry_count", 0)
        error = state.values.get("error")
        retrieved_tables = state.values.get("tables_used", [])
        
        # Log sanitized telemetry trace
        log_execution_trace(
            request_id=thread_id,
            question=original_question,
            visited_nodes=visited_nodes,
            retrieved_tables=retrieved_tables,
            generated_sql=generated_sql,
            validation_passed=validation_passed,
            execution_time_ms=execution_time_ms,
            retries=retries,
            error=error,
            model="gemini-3.5-flash"
        )
        
        return {
            "status": "completed",
            "thread_id": thread_id,
            "generated_sql": generated_sql,
            "final_answer": final_answer,
            "query_result": state.values.get("query_result"),
            "validation_passed": validation_passed,
            "error": error
        }
        
    except Exception as e:
        execution_time_ms = (time.time() - start_time) * 1000
        print(f"[QueryService Error] Resuming clarification failed: {e}")
        log_execution_trace(
            request_id=thread_id,
            question=original_question,
            visited_nodes=visited_nodes,
            retrieved_tables=[],
            generated_sql=None,
            validation_passed=False,
            execution_time_ms=execution_time_ms,
            retries=0,
            error=str(e),
            model="gemini-3.5-flash"
        )
        return {
            "status": "failed",
            "thread_id": thread_id,
            "error": f"Internal resume failure: {str(e)}"
        }
