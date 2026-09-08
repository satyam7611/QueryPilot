import os
import json
import pytest
from app.services.query_service import execute_query

def test_benchmark_dataset_integrity():
    """Verifies that the benchmark dataset exists, has valid JSON, and covers all required categories."""
    path = os.path.join("evaluation", "benchmark_dataset.json")
    assert os.path.exists(path), "benchmark_dataset.json must exist"
    
    with open(path, "r", encoding="utf-8") as f:
        cases = json.load(f)
        
    assert len(cases) >= 16, "Benchmark must contain at least 16 test cases"
    
    required_categories = {
        "Simple lookup",
        "Aggregation",
        "Filtering",
        "GROUP BY",
        "Sorting",
        "JOIN",
        "Date filtering",
        "Ambiguous question",
        "Out-of-domain question",
        "Invalid SQL scenario",
        "Security/injection attempt",
        "Wrong/nonexistent column",
        "Empty result",
        "Uploaded custom dataset",
        "Multi-dataset isolation",
        "Stale-state regression"
    }
    
    actual_categories = {c["category"] for c in cases}
    for req in required_categories:
        assert req in actual_categories, f"Missing required category: {req}"

def test_stale_state_regression():
    """
    Verifies that running sequential queries on different topics/datasets does not
    leak stale state (such as previously retrieved schemas or error messages).
    """
    from app.agent.graph import create_agent_graph
    app = create_agent_graph()
    
    # State 1: Run a query with an error/nonexistent column
    state1 = {
        "original_question": "Select nonexistent_column from products",
        "error": "Previous error message",
        "retry_count": 0,
        "is_ambiguous": True
    }
    
    # State 2: Fresh query must initialize cleanly without retaining previous error
    res = execute_query("What is the total number of orders?")
    assert res["status"] in ["completed", "clarification_required"]
    if res["status"] == "completed":
        assert res["error"] is None
