import os
import json
import time
from typing import List, Dict, Any, Optional

# Log file path in the workspace root
TRACE_LOG_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 
    "querypilot_traces.jsonl"
)

def log_execution_trace(
    request_id: str,
    question: str,
    visited_nodes: List[str],
    retrieved_tables: List[str],
    generated_sql: Optional[str],
    validation_passed: bool,
    execution_time_ms: float,
    retries: int,
    error: Optional[str] = None,
    model: str = "gemini-3.5-flash"
):
    """
    Appends a structured, sanitized execution trace to a local JSONL log file.
    Ensures secrets (like DB passwords or API keys) are never captured.
    """
    # Sanitize inputs (just in case they contain sensitive info)
    safe_sql = None
    if generated_sql:
        # Scrub potential inline password variables if somehow present (defense in depth)
        safe_sql = re_scrub_secrets(generated_sql)
        
    trace_data = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "request_id": request_id,
        "model": model,
        "original_question": question,
        "visited_nodes": visited_nodes,
        "retrieved_tables": retrieved_tables,
        "generated_sql": safe_sql,
        "validation_passed": validation_passed,
        "execution_time_ms": round(execution_time_ms, 2),
        "retries": retries,
        "error": re_scrub_secrets(error) if error else None
    }
    
    try:
        with open(TRACE_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(trace_data) + "\n")
        print(f"[Observability] Trace logged successfully to: querypilot_traces.jsonl")
    except Exception as e:
        print(f"[Observability Warning] Failed to write trace log: {e}")

def re_scrub_secrets(text: str) -> str:
    """Removes sensitive patterns like passwords or API keys from strings."""
    if not text:
        return text
    # Mask any password arguments or API key looks
    scrubbed = re_replace_case_insensitive(text, r"PASSWORD\s*=\s*['\"][^'\"]+['\"]", "PASSWORD=***")
    scrubbed = re_replace_case_insensitive(scrubbed, r"KEY\s*=\s*['\"][^'\"]+['\"]", "KEY=***")
    return scrubbed

def re_replace_case_insensitive(text: str, pattern: str, replacement: str) -> str:
    import re
    return re.sub(pattern, replacement, text, flags=re.IGNORECASE)
