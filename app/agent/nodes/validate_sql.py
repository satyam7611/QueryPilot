import os
from psycopg import connect
from app.agent.state import AgentState
from app.guardrails.sql_guard import is_safe_sql

def validate_sql(state: AgentState) -> dict:
    """
    Node that validates the safety and compilation of the generated SQL query.
    1. Static guardrail check (no write queries, SQL injections, or unapproved tables).
    2. Dynamic check using database EXPLAIN compilation test.
    Increments the retry_count on failure.
    """
    sql = state.get("generated_sql")
    retries = state.get("retry_count", 0)
    dataset_id = state.get("dataset_id")
    print(f"\n[Node: validate_sql] Validating SQL query (Attempt {retries + 1}/2)...")
    
    if not sql:
        return {
            "validation_result": False,
            "error": "No SQL query generated.",
            "retry_count": retries + 1
        }
        
    # 1. Static Guardrail Check
    if dataset_id:
        from app.services.dataset_service import get_dataset_table_name
        try:
            table_name = get_dataset_table_name(dataset_id)
            is_safe, guardrail_error = is_safe_sql(sql, allowed_tables={table_name})
        except Exception as e:
            is_safe, guardrail_error = False, f"Failed to verify dataset metadata: {e}"
    else:
        is_safe, guardrail_error = is_safe_sql(sql)
        
    if not is_safe:
        print(f" - Guardrail Block: {guardrail_error}")
        return {
            "validation_result": False,
            "error": f"Guardrail Rejection: {guardrail_error}",
            "retry_count": retries + 1
        }
    print(" - Static Guardrails: PASSED")
    
    # 2. Dynamic Compilation Check (EXPLAIN test)
    conn = None
    try:
        conn = connect(
            host=os.getenv("DB_HOST", "localhost"),
            port=os.getenv("DB_PORT", "5432"),
            user=os.getenv("DB_USER", "postgres"),
            password=os.getenv("DB_PASSWORD"),
            dbname=os.getenv("DB_NAME", "querypilot")
        )
        with conn.cursor() as cur:
            # Prepend EXPLAIN to test compilation without running the query
            explain_query = f"EXPLAIN {sql}"
            cur.execute(explain_query)
        print(" - DB Explain Compilation: PASSED")
        return {
            "validation_result": True,
            "error": None
        }
        
    except Exception as e:
        db_error = str(e).strip()
        print(f" - DB Compilation Failure: {db_error}")
        return {
            "validation_result": False,
            "error": f"Database Compilation Error: {db_error}",
            "retry_count": retries + 1
        }
    finally:
        if conn:
            conn.close()
