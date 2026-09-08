import json
from unittest.mock import MagicMock, patch

from app.services.query_service import execute_query
from app.utils.logger import build_telemetry_record, log_execution_trace


def test_structured_log_fields_and_redaction(tmp_path, monkeypatch):
    log_path = tmp_path / "querypilot_traces.jsonl"
    monkeypatch.setattr("app.utils.logger.TRACE_LOG_FILE", str(log_path))

    record = build_telemetry_record(
        request_id="req-123",
        session_id="sess-456",
        dataset_id="dataset_789",
        question="Show customers where api_key=sk-secret-123 and password='p@ssw0rd'",
        query_status="completed",
        rag_latency_ms=124.5,
        llm_latency_ms=875.2,
        sql_validation_result=True,
        retry_count=2,
        database_execution_ms=153.1,
        cache_hit=False,
        cache_miss=True,
        final_status="success",
        error=None,
        error_category=None,
        generated_sql="SELECT * FROM customers WHERE api_key = 'sk-secret-123' AND password = 'p@ssw0rd';",
        visited_nodes=["retrieve_schema", "generate_sql", "validate_sql", "execute_sql"],
        retrieved_tables=["customers"],
    )

    assert record["request_id"] == "req-123"
    assert record["session_id"] == "sess-456"
    assert record["dataset_id"] == "dataset_789"
    assert record["query_status"] == "completed"
    assert record["sql_validation_result"] is True
    assert record["retry_count"] == 2
    assert record["cache_hit"] is False
    assert record["cache_miss"] is True
    assert record["final_status"] == "success"
    assert "sk-secret-123" not in json.dumps(record)
    assert "p@ssw0rd" not in json.dumps(record)

    log_execution_trace(**record)
    payload = json.loads(log_path.read_text(encoding="utf-8").strip().splitlines()[-1])
    assert payload["request_id"] == "req-123"
    assert payload["dataset_id"] == "dataset_789"
    assert "sk-secret-123" not in json.dumps(payload)
    assert "p@ssw0rd" not in json.dumps(payload)


def test_successful_query_telemetry():
    mock_app = MagicMock()
    mock_app.stream.return_value = [{"retrieve_schema": {}, "generate_sql": {}, "validate_sql": {}}]
    mock_app.get_state.return_value = MagicMock(
        next=None,
        values={
            "generated_sql": "SELECT 1;",
            "final_answer": "Here is the answer.",
            "validation_result": True,
            "retry_count": 1,
            "error": None,
            "tables_used": ["customers"],
            "query_result": "result",
            "is_cache_hit": False,
            "dataset_id": "ds_success",
        },
    )

    with patch("app.services.query_service.get_graph", return_value=mock_app), \
         patch("app.services.query_service.log_execution_trace") as mock_logger:
        result = execute_query("How many customers are there?", dataset_id="ds_success", thread_id="req-success")

    assert result["status"] == "completed"
    assert result["thread_id"] == "req-success"
    mock_logger.assert_called_once()
    kwargs = mock_logger.call_args.kwargs
    assert kwargs["request_id"] == "req-success"
    assert kwargs["dataset_id"] == "ds_success"
    assert kwargs["query_status"] == "completed"
    assert kwargs["sql_validation_result"] is True
    assert kwargs["final_status"] == "success"
    assert kwargs["cache_hit"] is False
    assert kwargs["cache_miss"] is True


def test_failed_query_telemetry():
    mock_app = MagicMock()
    mock_app.stream.return_value = [{"retrieve_schema": {}}]
    mock_app.get_state.return_value = MagicMock(
        next=None,
        values={
            "generated_sql": "SELECT * FROM missing_table;",
            "final_answer": None,
            "validation_result": False,
            "retry_count": 2,
            "error": "Database Compilation Error: relation does not exist",
            "tables_used": ["missing_table"],
            "query_result": None,
            "is_cache_hit": False,
            "dataset_id": "ds_fail",
        },
    )

    with patch("app.services.query_service.get_graph", return_value=mock_app), \
         patch("app.services.query_service.log_execution_trace") as mock_logger:
        result = execute_query("Show me the missing table", dataset_id="ds_fail", thread_id="req-fail")

    assert result["status"] == "completed"
    kwargs = mock_logger.call_args.kwargs
    assert kwargs["query_status"] == "completed"
    assert kwargs["final_status"] == "failure"
    assert kwargs["error_category"] == "database_error"
    assert kwargs["sql_validation_result"] is False
    assert kwargs["retry_count"] == 2


def test_cache_hit_and_miss_telemetry():
    miss_record = build_telemetry_record(
        request_id="req-cache",
        dataset_id="dataset_cache",
        query_status="completed",
        cache_hit=False,
        cache_miss=True,
        final_status="success",
    )
    hit_record = build_telemetry_record(
        request_id="req-cache",
        dataset_id="dataset_cache",
        query_status="completed",
        cache_hit=True,
        cache_miss=False,
        final_status="success",
    )

    assert miss_record["cache_hit"] is False
    assert miss_record["cache_miss"] is True
    assert hit_record["cache_hit"] is True
    assert hit_record["cache_miss"] is False


def test_retry_telemetry():
    record = build_telemetry_record(
        request_id="req-retry",
        dataset_id="dataset_retry",
        retry_count=3,
        query_status="retrying",
        final_status="failure",
        error_category="validation_error",
        sql_validation_result=False,
    )

    assert record["retry_count"] == 3
    assert record["query_status"] == "retrying"
    assert record["error_category"] == "validation_error"
    assert record["final_status"] == "failure"


def test_secret_redaction_in_log_payload():
    payload = build_telemetry_record(
        request_id="req-secret",
        session_id="sess-secret",
        dataset_id="ds_secret",
        question="Use BYOK key=AIzaSyX123 and password=supersecret",
        generated_sql="SELECT * FROM customers WHERE password='supersecret' AND client_key='AIzaSyX123';",
        error="API key missing for BYOK provider: AIzaSyX123",
        query_status="failed",
        final_status="failure",
    )

    serialized = json.dumps(payload)
    assert "AIzaSyX123" not in serialized
    assert "supersecret" not in serialized
    assert "***" in serialized
