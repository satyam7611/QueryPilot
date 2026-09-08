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


def _finalize_query_telemetry(
    *,
    request_id: str,
    session_id: Optional[str],
    dataset_id: Optional[str],
    question: str,
    visited_nodes: list[str],
    retrieval_latency_ms: float,
    llm_latency_ms: float,
    validation_passed: bool,
    retry_count: int,
    database_execution_ms: float,
    cache_hit: bool,
    error: Optional[str],
    final_status: str,
    generated_sql: Optional[str],
    retrieved_tables: Optional[list[str]],
    query_status: str,
    cache_miss: Optional[bool] = None,
    model: Optional[str] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    error_category = None
    if error:
        err = error.lower()
        if any(token in err for token in ["quota", "rate limit", "429", "api key", "byok", "llm", "gemini", "503", "unavailable"]):
            error_category = "llm_error"
        elif any(token in err for token in ["guardrail", "access denied", "forbidden", "invalid sql", "validation"]):
            error_category = "validation_error"
        elif any(token in err for token in ["database", "relation does not exist", "syntax", "compile", "explain", "permission", "read-only"]):
            error_category = "database_error"
        elif any(token in err for token in ["cache", "ttl", "stale"]):
            error_category = "cache_error"
        else:
            error_category = "unknown"

    actual_cache_miss = cache_miss if cache_miss is not None else (not cache_hit)

    return log_execution_trace(
        request_id=request_id,
        session_id=session_id or request_id,
        dataset_id=dataset_id,
        question=question,
        query_status=query_status,
        rag_latency_ms=retrieval_latency_ms,
        llm_latency_ms=llm_latency_ms,
        sql_validation_result=validation_passed,
        retry_count=retry_count,
        database_execution_ms=database_execution_ms,
        cache_hit=cache_hit,
        cache_miss=actual_cache_miss,
        final_status=final_status,
        error=error,
        error_category=error_category,
        generated_sql=generated_sql,
        visited_nodes=visited_nodes,
        retrieved_tables=retrieved_tables,
        model=model or "gemini-3.5-flash",
    )


def execute_query(
    question: str,
    dataset_id: Optional[str] = None,
    api_key: Optional[str] = None,
    thread_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Submits a query to the LangGraph Text-to-SQL workflow.
    Handles RAG context, API key routing, and paused clarification interrupts.
    """
    app = get_graph()

    active_thread = thread_id or str(uuid.uuid4())
    config = {"configurable": {"thread_id": active_thread, "api_key": api_key}}

    visited_nodes = []
    start_time = time.time()
    retrieval_latency_ms = 0.0
    llm_latency_ms = 0.0
    database_execution_ms = 0.0

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
        "final_answer": None,
        "is_cache_hit": False,
    }

    try:
        stream = app.stream(initial_state, config, stream_mode="updates")
        for event in stream:
            for node_name in event.keys():
                if node_name not in ["__metadata__", "__root__"]:
                    visited_nodes.append(node_name)

        state = app.get_state(config)

        if state.next and state.next[0] == "ask_clarification":
            return {
                "status": "clarification_required",
                "thread_id": active_thread,
                "question": state.values.get("clarification_question"),
                "options": state.values.get("options", []),
            }

        execution_time_ms = (time.time() - start_time) * 1000
        generated_sql = state.values.get("generated_sql")
        final_answer = state.values.get("final_answer")
        validation_passed = state.values.get("validation_result", False)
        retries = state.values.get("retry_count", 0)
        error = state.values.get("error")
        retrieved_tables = state.values.get("tables_used", [])
        cache_hit = bool(state.values.get("is_cache_hit", False))
        final_status = "success" if validation_passed and not error and final_answer else "failure"
        query_status = "completed" if final_status == "success" else "completed"

        _finalize_query_telemetry(
            request_id=active_thread,
            session_id=active_thread,
            dataset_id=dataset_id,
            question=question,
            visited_nodes=visited_nodes,
            retrieval_latency_ms=retrieval_latency_ms,
            llm_latency_ms=llm_latency_ms,
            validation_passed=validation_passed,
            retry_count=retries,
            database_execution_ms=database_execution_ms or execution_time_ms,
            cache_hit=cache_hit,
            error=error,
            final_status=final_status,
            generated_sql=generated_sql,
            retrieved_tables=retrieved_tables,
            query_status=query_status,
        )

        return {
            "status": "completed",
            "thread_id": active_thread,
            "generated_sql": generated_sql,
            "final_answer": final_answer,
            "query_result": state.values.get("query_result"),
            "validation_passed": validation_passed,
            "error": error,
        }

    except Exception as e:
        execution_time_ms = (time.time() - start_time) * 1000
        print(f"[QueryService Error] Execution failed: {e}")
        _finalize_query_telemetry(
            request_id=active_thread,
            session_id=active_thread,
            dataset_id=dataset_id,
            question=question,
            visited_nodes=visited_nodes,
            retrieval_latency_ms=retrieval_latency_ms,
            llm_latency_ms=llm_latency_ms,
            validation_passed=False,
            retry_count=0,
            database_execution_ms=database_execution_ms or execution_time_ms,
            cache_hit=False,
            cache_miss=True,
            error=str(e),
            final_status="failure",
            generated_sql=None,
            retrieved_tables=[],
            query_status="failed",
        )
        return {
            "status": "failed",
            "thread_id": active_thread,
            "error": f"Internal execution failure: {str(e)}",
        }


def resume_clarification(
    thread_id: str,
    choice: str,
    api_key: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Resumes a paused LangGraph clarification thread with the user's choice.
    """
    app = get_graph()
    config = {"configurable": {"thread_id": thread_id, "api_key": api_key}}

    pre_state = app.get_state(config)
    original_question = pre_state.values.get("original_question", "Resume clarification query")
    dataset_id = pre_state.values.get("dataset_id")

    visited_nodes = ["ask_clarification"]
    start_time = time.time()

    try:
        stream = app.stream(Command(resume=choice), config, stream_mode="updates")
        for event in stream:
            for node_name in event.keys():
                if node_name not in ["__metadata__", "__root__"]:
                    visited_nodes.append(node_name)

        state = app.get_state(config)

        execution_time_ms = (time.time() - start_time) * 1000
        generated_sql = state.values.get("generated_sql")
        final_answer = state.values.get("final_answer")
        validation_passed = state.values.get("validation_result", False)
        retries = state.values.get("retry_count", 0)
        error = state.values.get("error")
        retrieved_tables = state.values.get("tables_used", [])
        cache_hit = bool(state.values.get("is_cache_hit", False))
        final_status = "success" if validation_passed and not error and final_answer else "failure"

        _finalize_query_telemetry(
            request_id=thread_id,
            session_id=thread_id,
            dataset_id=dataset_id,
            question=original_question,
            visited_nodes=visited_nodes,
            retrieval_latency_ms=0.0,
            llm_latency_ms=0.0,
            validation_passed=validation_passed,
            retry_count=retries,
            database_execution_ms=execution_time_ms,
            cache_hit=cache_hit,
            error=error,
            final_status=final_status,
            generated_sql=generated_sql,
            retrieved_tables=retrieved_tables,
            query_status="completed",
        )

        return {
            "status": "completed",
            "thread_id": thread_id,
            "generated_sql": generated_sql,
            "final_answer": final_answer,
            "query_result": state.values.get("query_result"),
            "validation_passed": validation_passed,
            "error": error,
        }

    except Exception as e:
        execution_time_ms = (time.time() - start_time) * 1000
        print(f"[QueryService Error] Resuming clarification failed: {e}")
        _finalize_query_telemetry(
            request_id=thread_id,
            session_id=thread_id,
            dataset_id=dataset_id,
            question=original_question,
            visited_nodes=visited_nodes,
            retrieval_latency_ms=0.0,
            llm_latency_ms=0.0,
            validation_passed=False,
            retry_count=0,
            database_execution_ms=execution_time_ms,
            cache_hit=False,
            error=str(e),
            final_status="failure",
            generated_sql=None,
            retrieved_tables=[],
            query_status="failed",
        )
        return {
            "status": "failed",
            "thread_id": thread_id,
            "error": f"Internal resume failure: {str(e)}",
        }
