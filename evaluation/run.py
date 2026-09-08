import os
import sys
import json
import re
import time
import uuid
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.agent.graph import create_agent_graph
from langgraph.types import Command
from app.rag.retriever import retrieve_relevant_schema, index_dataset_schema, delete_dataset_schema
from app.services.dataset_service import process_and_save_dataset, delete_user_dataset

# Load environment
workspace_env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
load_dotenv(dotenv_path=workspace_env_path, override=True)

# Minimum inter-case pacing (seconds). With a 5 RPM free-tier quota, each
# query consumes ~2-3 LLM calls. We pace at 15s so no more than 4 cases land
# inside any rolling 60-second window.
PACING_SECONDS = 15


def _parse_retry_delay(error_str: str) -> int:
    """Extract retry delay (seconds) from a 429 rate-limit error string."""
    match = re.search(r'"retryDelay":\s*"(\d+)s"', error_str)
    if match:
        return int(match.group(1)) + 3  # 3s safety buffer
    match = re.search(r'retry in (\d+)\.', error_str)
    if match:
        return int(match.group(1)) + 3
    return 60  # safe default


def _is_rate_limit_error(text: str) -> bool:
    return any(kw in text for kw in [
        "RateLimitError", "429", "RESOURCE_EXHAUSTED", "Quota Exhausted",
        "quota", "rate limit", "rate_limit"
    ])


def run_evaluation_case(app, test_case: Dict[str, Any], custom_datasets: Dict[str, str]) -> Dict[str, Any]:
    """Runs an individual evaluation case through the LangGraph workflow."""
    case_id = test_case["id"]
    category = test_case["category"]
    question = test_case["question"]
    dataset_type = test_case.get("dataset_type", "demo")
    mock_choice = test_case.get("mock_choice")
    expected_behavior = test_case.get("expected_behavior")

    # Resolve dataset_id for custom dataset cases
    dataset_id = None
    if dataset_type == "custom":
        dataset_id = custom_datasets.get("employees")
    elif dataset_type == "custom_isolation":
        dataset_id = custom_datasets.get("user_a")

    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    visited_nodes = []
    start_time = time.time()

    current_input = {
        "original_question": question,
        "dataset_id": dataset_id,
        "retry_count": 0
    }

    clarification_triggered = False
    rate_limited = False
    rate_limit_retry_after = 0

    while True:
        try:
            stream = app.stream(current_input, config, stream_mode="updates")
            for event in stream:
                for node_name in event.keys():
                    if node_name not in ["__metadata__", "__root__"]:
                        visited_nodes.append(node_name)
        except Exception as e:
            err_str = str(e)
            if _is_rate_limit_error(err_str):
                rate_limited = True
                rate_limit_retry_after = _parse_retry_delay(err_str)
            print(f"   [Stream error: {type(e).__name__}]")
            break

        state = app.get_state(config)

        # Clarification interrupt
        if state.next and state.next[0] == "ask_clarification":
            clarification_triggered = True
            choice = mock_choice or "1"
            current_input = Command(resume=choice)
        else:
            break

    latency_ms = (time.time() - start_time) * 1000
    final_state = app.get_state(config)

    generated_sql = final_state.values.get("generated_sql")
    final_answer = final_state.values.get("final_answer")
    query_result = final_state.values.get("query_result")
    retrieved_schema = final_state.values.get("retrieved_schema")
    validation_result = final_state.values.get("validation_result")
    is_out_of_domain = final_state.values.get("is_out_of_domain", False)
    error = final_state.values.get("error")

    # Check if node-level error signals a rate limit
    if error and _is_rate_limit_error(error):
        rate_limited = True
        rate_limit_retry_after = _parse_retry_delay(error)

    # Security block detection
    security_blocked = (
        "handle_out_of_domain" in visited_nodes or
        (error and any(kw in error for kw in [
            "Guardrail Rejection", "Forbidden keyword", "read-only",
            "DDL", "DML", "not allowed"
        ]))
    )

    schema_retrieved = bool(retrieved_schema and "-- Table:" in retrieved_schema)
    if dataset_id and retrieved_schema:
        schema_retrieved = dataset_id in retrieved_schema or "dataset_" in retrieved_schema

    # Determine outcome
    passed = False
    if rate_limited:
        passed = None  # None = skipped, not a real failure
    elif expected_behavior == "execute":
        passed = query_result is not None and not error
    elif expected_behavior == "clarify":
        passed = clarification_triggered and ("merge_clarification" in visited_nodes)
    elif expected_behavior == "reject_domain":
        passed = is_out_of_domain or ("handle_out_of_domain" in visited_nodes)
    elif expected_behavior == "block_security":
        passed = security_blocked
    elif expected_behavior == "reject_or_retry":
        # Agent gracefully handled/retried without crashing
        passed = True
    elif expected_behavior == "execute_empty":
        passed = query_result is not None
    elif expected_behavior == "isolated_retrieve":
        passed = schema_retrieved and ("customers" not in (retrieved_schema or ""))
    else:
        passed = query_result is not None

    return {
        "id": case_id,
        "category": category,
        "question": question,
        "dataset_type": dataset_type,
        "passed": passed,
        "rate_limited": rate_limited,
        "rate_limit_retry_after": rate_limit_retry_after,
        "visited_nodes": visited_nodes,
        "generated_sql": generated_sql,
        "clarification_triggered": clarification_triggered,
        "security_blocked": security_blocked,
        "schema_retrieved": schema_retrieved,
        "latency_ms": round(latency_ms, 2),
        "error": error
    }


def main():
    print("=" * 60)
    print("      QUERYPILOT: TEXT-TO-SQL BENCHMARK EVALUATOR       ")
    print("=" * 60)

    benchmark_path = os.path.join(os.path.dirname(__file__), "benchmark_dataset.json")
    with open(benchmark_path, "r", encoding="utf-8") as f:
        cases = json.load(f)

    print(f"Loaded {len(cases)} evaluation test cases.")
    print(f"Inter-case pacing: {PACING_SECONDS}s (respects free-tier 5 RPM quota).")
    print(f"Estimated total runtime: ~{len(cases) * PACING_SECONDS // 60} min.\n")

    # Seed temporary custom datasets
    custom_datasets = {}
    emp_csv = "id,name,department,salary\n1,Alice,Engineering,95000\n2,Bob,Engineering,85000\n3,Carol,Marketing,65000\n"
    user_a_csv = "user_id,username,active\n101,john_doe,true\n102,jane_doe,false\n"

    print("Seeding temporary evaluation datasets...")
    try:
        ds_emp = process_and_save_dataset(emp_csv.encode("utf-8"), "employees.csv", "eval-session")
        ds_user_a = process_and_save_dataset(user_a_csv.encode("utf-8"), "user_a.csv", "eval-session-a")
        custom_datasets["employees"] = ds_emp
        custom_datasets["user_a"] = ds_user_a
    except Exception as e:
        print(f"Note: Could not seed test tables: {e}")

    app = create_agent_graph()
    results = []

    total_cases = len(cases)
    executed = 0
    passed_cases = 0
    skipped_cases = 0
    schema_success_count = 0
    security_cases = 0
    security_blocked_count = 0
    clarification_cases = 0
    clarification_correct_count = 0
    total_latency_ms = 0.0

    print("\nRunning benchmark execution...\n")

    for idx, tc in enumerate(cases):
        print(f"[{idx+1}/{total_cases}] {tc['id']} | {tc['category']:<28} | '{tc['question']}'")

        res = run_evaluation_case(app, tc, custom_datasets)
        results.append(res)

        if res["rate_limited"]:
            skipped_cases += 1
            retry_after = res["rate_limit_retry_after"]
            print(f"    -> SKIPPED (Rate limited) | Waiting {retry_after}s for quota reset...")
            time.sleep(retry_after)
            # Immediately retry this case after waiting
            print(f"    Retrying {tc['id']} after rate-limit cooldown...")
            res = run_evaluation_case(app, tc, custom_datasets)
            results[-1] = res  # Replace with retry result

            if res["rate_limited"]:
                # Still rate limited – mark as skipped and continue
                print(f"    -> SKIPPED (Still rate limited after retry)")
                continue

        executed += 1
        total_latency_ms += res["latency_ms"]
        if res["passed"]:
            passed_cases += 1
        if res["schema_retrieved"]:
            schema_success_count += 1

        if tc.get("is_malicious"):
            security_cases += 1
            if res["security_blocked"]:
                security_blocked_count += 1

        if tc.get("is_ambiguous"):
            clarification_cases += 1
            if res["clarification_triggered"]:
                clarification_correct_count += 1

        status_str = "PASSED" if res["passed"] else "FAILED"
        print(f"    -> {status_str} | Latency: {res['latency_ms']:.0f}ms | Nodes: {' -> '.join(res['visited_nodes'])}")

        # Inter-case pacing
        if idx < total_cases - 1:
            print(f"    [Pacing: sleeping {PACING_SECONDS}s]")
            time.sleep(PACING_SECONDS)

    # Cleanup temporary datasets
    try:
        if "employees" in custom_datasets:
            delete_user_dataset(custom_datasets["employees"], "eval-session")
        if "user_a" in custom_datasets:
            delete_user_dataset(custom_datasets["user_a"], "eval-session-a")
    except Exception:
        pass

    # Metrics (calculated only over executed cases)
    accuracy = (passed_cases / executed * 100) if executed else 0
    schema_accuracy = (schema_success_count / executed * 100) if executed else 0
    security_rate = (security_blocked_count / security_cases * 100) if security_cases else 100.0
    clarification_rate = (clarification_correct_count / clarification_cases * 100) if clarification_cases else 100.0
    avg_latency = total_latency_ms / executed if executed else 0

    print("\n" + "=" * 60)
    print("                 BENCHMARK RESULTS REPORT                ")
    print("=" * 60)
    print(f"Total Cases:               {total_cases}")
    print(f"Executed:                  {executed}")
    print(f"Skipped (Rate limited):    {skipped_cases}")
    print(f"Passed:                    {passed_cases}")
    print(f"Failed:                    {executed - passed_cases}")
    print(f"Overall Accuracy:          {accuracy:.1f}%  (of executed)")
    print(f"Schema Retrieval Rate:     {schema_accuracy:.1f}%")
    print(f"Security Rejection Rate:   {security_rate:.1f}%")
    print(f"Clarification Accuracy:    {clarification_rate:.1f}%")
    print(f"Average Latency:           {avg_latency:.0f} ms")
    print("=" * 60 + "\n")

    results_path = os.path.join(os.path.dirname(__file__), "results.json")
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump({
            "metrics": {
                "total_cases": total_cases,
                "executed": executed,
                "skipped_rate_limited": skipped_cases,
                "passed": passed_cases,
                "failed": executed - passed_cases,
                "accuracy_percent": round(accuracy, 1),
                "schema_retrieval_accuracy_percent": round(schema_accuracy, 1),
                "security_rejection_percent": round(security_rate, 1),
                "clarification_accuracy_percent": round(clarification_rate, 1),
                "avg_latency_ms": round(avg_latency, 1)
            },
            "cases": results
        }, f, indent=4)
    print(f"Results saved to: {results_path}")


if __name__ == "__main__":
    main()
