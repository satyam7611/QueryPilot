from app.agent.state import AgentState
from app.tools.postgres_tool import execute_readonly_sql

def execute_sql(state: AgentState) -> dict:
    """
    Node that executes the validated SQL query against PostgreSQL
    by calling our decoupled database tool.
    """
    sql = state.get("generated_sql")
    print(f"\n[Node: execute_sql] Executing query via Database Tool...")
    
    # Invoke the PostgreSQL tool
    result = execute_readonly_sql.invoke({"sql_query": sql})
    
    # Check if the tool returned an error string
    if result.startswith("Database Error:"):
        print(f" - Tool returned database error: {result}")
        return {
            "error": result,
            "validation_result": False  # Triggers self-correction loop
        }
    
    print(" - Tool execution succeeded.")
    return {
        "query_result": result,
        "error": None
    }
