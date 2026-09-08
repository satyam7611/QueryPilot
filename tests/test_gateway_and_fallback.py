import os
import pytest
from unittest.mock import MagicMock, patch
from pydantic import BaseModel

from app.services.query_service import _finalize_query_telemetry, execute_query
from app.llm.gateway import (
    resolve_api_key_for_model,
    get_candidate_models,
    is_fallback_worthy_error,
    _parse_structured_output,
    query_llm,
)


class DummyOutput(BaseModel):
    summary: str
    confidence: float


def test_finalize_query_telemetry_accepts_cache_miss_and_kwargs():
    """Verifies that _finalize_query_telemetry accepts cache_miss and unexpected kwargs without error."""
    # Test with explicit cache_miss=True
    record1 = _finalize_query_telemetry(
        request_id="test-1",
        session_id="test-1",
        dataset_id=None,
        question="test question",
        visited_nodes=["node1"],
        retrieval_latency_ms=10.0,
        llm_latency_ms=20.0,
        validation_passed=False,
        retry_count=0,
        database_execution_ms=5.0,
        cache_hit=False,
        cache_miss=True,
        error="test error",
        final_status="failure",
        generated_sql=None,
        retrieved_tables=[],
        query_status="failed",
        unexpected_future_arg="ignored_safely",
    )
    assert record1["cache_hit"] is False
    assert record1["cache_miss"] is True

    # Test without cache_miss (inferred from cache_hit=True)
    record2 = _finalize_query_telemetry(
        request_id="test-2",
        session_id="test-2",
        dataset_id=None,
        question="test question",
        visited_nodes=["node1"],
        retrieval_latency_ms=10.0,
        llm_latency_ms=20.0,
        validation_passed=True,
        retry_count=0,
        database_execution_ms=5.0,
        cache_hit=True,
        error=None,
        final_status="success",
        generated_sql="SELECT 1;",
        retrieved_tables=[],
        query_status="completed",
    )
    assert record2["cache_hit"] is True
    assert record2["cache_miss"] is False


def test_execute_query_catches_unhandled_exception_without_telemetry_crash():
    """Verifies that when graph execution raises an unhandled exception, execute_query safely returns a failed result."""
    mock_app = MagicMock()
    mock_app.stream.side_effect = RuntimeError("503 Service Unavailable: High Demand")

    with patch("app.services.query_service.get_graph", return_value=mock_app):
        result = execute_query("Test question triggering 503")

    assert result["status"] == "failed"
    assert "Internal execution failure" in result["error"]
    assert "503 Service Unavailable" in result["error"]


def test_resolve_api_key_for_model(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "env_gemini_key")
    monkeypatch.setenv("GROQ_API_KEY", "env_groq_key")

    # Default to env keys
    assert resolve_api_key_for_model("gemini/gemini-2.5-flash") == "env_gemini_key"
    assert resolve_api_key_for_model("groq/llama-3.3-70b-versatile") == "env_groq_key"

    # User BYOK Groq key (starts with gsk_)
    assert resolve_api_key_for_model("groq/llama-3.3-70b-versatile", user_api_key="gsk_user123") == "gsk_user123"
    # User BYOK Gemini key should NOT be used for Groq
    assert resolve_api_key_for_model("groq/llama-3.3-70b-versatile", user_api_key="AIzaSyUserKey") == "env_groq_key"

    # User BYOK Gemini key
    assert resolve_api_key_for_model("gemini/gemini-2.5-flash", user_api_key="AIzaSyUserKey") == "AIzaSyUserKey"
    # User BYOK Groq key should NOT be used for Gemini
    assert resolve_api_key_for_model("gemini/gemini-2.5-flash", user_api_key="gsk_user123") == "env_gemini_key"


def test_is_fallback_worthy_error():
    assert is_fallback_worthy_error(Exception("503 Service Unavailable: High Demand")) is True
    assert is_fallback_worthy_error(Exception("Spikes in demand are usually temporary")) is True
    assert is_fallback_worthy_error(Exception("429 Resource has been exhausted (e.g. check quota)")) is True
    assert is_fallback_worthy_error(Exception("Gateway Timeout 504")) is True
    assert is_fallback_worthy_error(ValueError("syntax error in prompt template")) is False


def test_parse_structured_output_handles_markdown_and_dict():
    # Markdown fenced json
    fenced = '```json\n{"summary": "hello", "confidence": 0.95}\n```'
    parsed = _parse_structured_output(fenced, DummyOutput)
    assert parsed.summary == "hello"
    assert parsed.confidence == 0.95

    # Direct dict
    raw_dict = {"summary": "world", "confidence": 0.88}
    parsed2 = _parse_structured_output(raw_dict, DummyOutput)
    assert parsed2.summary == "world"


@patch("app.llm.gateway.litellm.completion")
def test_query_llm_fallback_on_503(mock_completion, monkeypatch):
    """Verifies that when primary model returns 503, query_llm fails over to fallback model."""
    monkeypatch.setenv("GEMINI_API_KEY", "test_gemini")
    monkeypatch.setenv("GROQ_API_KEY", "test_groq")

    # First call (primary model) fails with 503
    # Second call (fallback model) succeeds
    mock_response = MagicMock()
    mock_response.choices = [MagicMock(message=MagicMock(content="Fallback answer"))]

    mock_completion.side_effect = [
        Exception("503 Service Unavailable: This model is currently experiencing high demand."),
        mock_response
    ]

    messages = [{"role": "user", "content": "Hello"}]
    answer = query_llm(messages=messages, model="gemini/gemini-2.5-flash")

    assert answer == "Fallback answer"
    assert mock_completion.call_count == 2
