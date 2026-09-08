from app.agent.state import AgentState
from app.tools.postgres_tool import execute_readonly_sql
from app.core.cache import query_cache

def execute_sql(state: AgentState) -> dict:
    """
    Node that executes the validated SQL query against PostgreSQL
    by checking the result cache first and delegating to the database tool on miss.
    """
    sql = state.get("generated_sql")
    dataset_id = state.get("dataset_id")
    schema_hash = state.get("schema_hash")
    
    if not sql:
        return {
            "error": "No SQL query to execute.",
            "validation_result": False,
            "is_cache_hit": False
        }
        
    # 1. Check Query Result Cache
    cached_result = query_cache.get(dataset_id, schema_hash, sql)
    if cached_result is not None:
        print(f"\n[Node: execute_sql] Cache HIT for dataset '{dataset_id or 'demo'}'. Returning cached results.")
        return {
            "query_result": cached_result,
            "error": None,
            "is_cache_hit": True
        }
        
    print(f"\n[Node: execute_sql] Cache MISS. Executing query via Database Tool...")
    
    # 2. Invoke the PostgreSQL tool
    result = execute_readonly_sql.invoke({"sql_query": sql})
    
    # 3. Check if the tool returned an error string
    if result.startswith("Database Error:"):
        print(f" - Tool returned database error: {result}")
        return {
            "error": result,
            "validation_result": False,  # Triggers self-correction loop
            "is_cache_hit": False
        }
    
    # 4. Cache successful result
    query_cache.set(dataset_id, schema_hash, sql, result)
    print(" - Tool execution succeeded and cached.")
    return {
        "query_result": result,
        "error": None,
        "is_cache_hit": False
    }
