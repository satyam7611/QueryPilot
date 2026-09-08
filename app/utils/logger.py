import os
import json
import re
import time
from typing import Any, Dict, List, Optional

# Log file path in the workspace root
TRACE_LOG_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "querypilot_traces.jsonl",
)


def _mask_secrets(value: str) -> str:
    """Redacts common secret values from log text while keeping the record useful."""
    if not value:
        return value

    scrubbed = value
    scrubbed = re.sub(
        r"(?i)(?P<name>(?:api|client|db|readonly|gemini|byok|user|access)[_-]?(?:key|secret|token)|(?:byok\s+key)|(?:api\s*key)|(?:password)|(?:passwd)|(?:pwd)|(?:secret)|(?:token))\s*(?:=|:)\s*['\"]?(?P<value>[^'\"\s,;]+)['\"]?",
        lambda m: f"{m.group('name')}=" + "***",
        scrubbed,
    )
    scrubbed = re.sub(
        r"(?i)(?:\b(?:byok\s+key|api\s*key|client\s*key|gemini\s*api\s*key|db\s*password|readonly\s*password|password|secret|token)\s*=?\s*['\"]?)([A-Za-z0-9\-_\.]{8,})(?=['\"\s,;]|$)",
        lambda m: re.sub(r"([A-Za-z0-9\-_\.]{8,})$", "***", m.group(0)),
        scrubbed,
    )
    scrubbed = re.sub(
        r"(?i)\b(?:AIza[0-9A-Za-z\-_]{4,}|sk-[A-Za-z0-9]{4,}|ghp_[A-Za-z0-9]{10,}|ya29\.[A-Za-z0-9\-_]+)\b",
        "***",
        scrubbed,
    )
    scrubbed = re.sub(
        r"(?i)(?<=: )AIza[0-9A-Za-z\-_]+",
        "***",
        scrubbed,
    )
    return scrubbed


def sanitize_for_logging(value: Any) -> Any:
    """Recursively strips sensitive values from structured payloads before writing logs."""
    if isinstance(value, str):
        return _mask_secrets(value)
    if isinstance(value, list):
        return [sanitize_for_logging(item) for item in value]
    if isinstance(value, dict):
        return {str(k): sanitize_for_logging(v) for k, v in value.items()}
    return value


def re_scrub_secrets(text: str) -> str:
    """Backward-compatible alias for secret scrubbing used by older code paths."""
    return _mask_secrets(text) if text else text


def re_replace_case_insensitive(text: str, pattern: str, replacement: str) -> str:
    return re.sub(pattern, replacement, text, flags=re.IGNORECASE)


def classify_error_category(error: Optional[str], *, query_status: Optional[str] = None) -> Optional[str]:
    """Maps error text to a lightweight telemetry category without exposing details."""
    if not error:
        return None

    err = error.lower()
    if any(token in err for token in ["quota", "rate limit", "429", "api key", "byok", "llm", "gemini"]):
        return "llm_error"
    if any(token in err for token in ["guardrail", "access denied", "forbidden", "invalid sql", "validation"]) :
        return "validation_error"
    if any(token in err for token in ["database", "relation does not exist", "syntax", "compile", "explain", "permission", "read-only"]):
        return "database_error"
    if any(token in err for token in ["cache", "ttl", "stale"]):
        return "cache_error"
    if query_status == "retrying":
        return "validation_error"
    return "unknown"


def build_telemetry_record(
    *,
    request_id: Optional[str] = None,
    session_id: Optional[str] = None,
    dataset_id: Optional[str] = None,
    question: Optional[str] = None,
    query_status: Optional[str] = "completed",
    rag_latency_ms: float = 0.0,
    llm_latency_ms: float = 0.0,
    sql_validation_result: Optional[bool] = None,
    retry_count: int = 0,
    database_execution_ms: float = 0.0,
    cache_hit: bool = False,
    cache_miss: bool = False,
    final_status: Optional[str] = None,
    error: Optional[str] = None,
    error_category: Optional[str] = None,
    generated_sql: Optional[str] = None,
    visited_nodes: Optional[List[str]] = None,
    retrieved_tables: Optional[List[str]] = None,
    model: str = "gemini-3.5-flash",
    **kwargs,
) -> Dict[str, Any]:
    """Builds a sanitized structured log record with the observability fields required by Phase 5."""
    record = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "request_id": request_id or kwargs.get("thread_id") or str(time.time_ns()),
        "session_id": session_id or kwargs.get("session_id") or request_id or kwargs.get("thread_id") or str(time.time_ns()),
        "dataset_id": dataset_id,
        "model": model,
        "query_status": query_status,
        "rag_latency_ms": round(float(rag_latency_ms or 0.0), 2),
        "llm_latency_ms": round(float(llm_latency_ms or 0.0), 2),
        "sql_validation_result": sql_validation_result,
        "retry_count": int(retry_count or 0),
        "database_execution_ms": round(float(database_execution_ms or 0.0), 2),
        "cache_hit": bool(cache_hit),
        "cache_miss": bool(cache_miss),
        "final_status": final_status or ("success" if query_status in {"completed", "resolved"} and not error else "failure"),
        "error_category": error_category or classify_error_category(error, query_status=query_status),
        "original_question": sanitize_for_logging(question),
        "visited_nodes": sanitize_for_logging(visited_nodes or []),
        "retrieved_tables": sanitize_for_logging(retrieved_tables or []),
        "generated_sql": sanitize_for_logging(generated_sql),
        "validation_passed": bool(sql_validation_result) if sql_validation_result is not None else None,
        "execution_time_ms": round(float(rag_latency_ms or 0.0) + float(llm_latency_ms or 0.0) + float(database_execution_ms or 0.0), 2),
        "error": sanitize_for_logging(error),
    }
    return sanitize_for_logging(record)


def log_execution_trace(*args, **kwargs):
    """Writes a sanitized structured telemetry record to the existing JSONL trace file."""
    legacy_fields = {
        "request_id": None,
        "question": None,
        "visited_nodes": None,
        "retrieved_tables": None,
        "generated_sql": None,
        "validation_passed": None,
        "execution_time_ms": 0.0,
        "retries": 0,
        "error": None,
        "model": "gemini-3.5-flash",
    }

    if args:
        if len(args) > 0:
            legacy_fields["request_id"] = args[0]
        if len(args) > 1:
            legacy_fields["question"] = args[1]
        if len(args) > 2:
            legacy_fields["visited_nodes"] = args[2]
        if len(args) > 3:
            legacy_fields["retrieved_tables"] = args[3]
        if len(args) > 4:
            legacy_fields["generated_sql"] = args[4]
        if len(args) > 5:
            legacy_fields["validation_passed"] = args[5]
        if len(args) > 6:
            legacy_fields["execution_time_ms"] = args[6]
        if len(args) > 7:
            legacy_fields["retries"] = args[7]
        if len(args) > 8:
            legacy_fields["error"] = args[8]
        if len(args) > 9:
            legacy_fields["model"] = args[9]

    legacy_fields.update({k: v for k, v in kwargs.items() if v is not None})
    record = build_telemetry_record(
        request_id=legacy_fields.get("request_id"),
        session_id=legacy_fields.get("session_id"),
        dataset_id=legacy_fields.get("dataset_id"),
        question=legacy_fields.get("question"),
        query_status=legacy_fields.get("query_status", "completed"),
        rag_latency_ms=legacy_fields.get("rag_latency_ms", 0.0),
        llm_latency_ms=legacy_fields.get("llm_latency_ms", 0.0),
        sql_validation_result=legacy_fields.get("sql_validation_result", legacy_fields.get("validation_passed")),
        retry_count=legacy_fields.get("retry_count", legacy_fields.get("retries", 0)),
        database_execution_ms=legacy_fields.get("database_execution_ms", legacy_fields.get("execution_time_ms", 0.0)),
        cache_hit=legacy_fields.get("cache_hit", False),
        cache_miss=legacy_fields.get("cache_miss", False),
        final_status=legacy_fields.get("final_status"),
        error=legacy_fields.get("error"),
        error_category=legacy_fields.get("error_category"),
        generated_sql=legacy_fields.get("generated_sql"),
        visited_nodes=legacy_fields.get("visited_nodes"),
        retrieved_tables=legacy_fields.get("retrieved_tables"),
        model=legacy_fields.get("model", "gemini-3.5-flash"),
    )

    try:
        with open(TRACE_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as exc:
        print(f"[Observability Warning] Failed to write trace log: {exc}")
    return record
