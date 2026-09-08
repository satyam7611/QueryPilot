import os
from langchain_core.tools import tool
from psycopg import connect
from dotenv import load_dotenv

# Load env variables explicitly
workspace_env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env")
load_dotenv(dotenv_path=workspace_env_path)

def get_readonly_db_connection():
    """
    Establishes a dedicated read-only connection to the PostgreSQL database.
    Configures session-level read-only transactions and strict execution timeouts.
    """
    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "5432")
    user = os.getenv("DB_READONLY_USER", os.getenv("DB_USER", "postgres"))
    password = os.getenv("DB_READONLY_PASSWORD", os.getenv("DB_PASSWORD"))
    dbname = os.getenv("DB_NAME", "querypilot")
    
    conn = connect(
        host=host,
        port=port,
        user=user,
        password=password,
        dbname=dbname
    )
    
    # Configure session-level defense in depth:
    # 1. Enforce strict statement timeout (10 seconds / 10000ms)
    # 2. Enforce transaction read-only mode so DDL/DML write operations are rejected at DB level
    with conn.cursor() as cur:
        cur.execute("SET statement_timeout = 10000;")
        cur.execute("SET default_transaction_read_only = ON;")
    conn.commit()
    
    return conn

@tool
def execute_readonly_sql(sql_query: str) -> str:
    """
    Executes a read-only SELECT SQL query against the PostgreSQL database.
    Input must be a valid, read-only SQL SELECT statement.
    Returns the columns and rows as a formatted string, or an error message.
    """
    conn = None
    try:
        conn = get_readonly_db_connection()
        with conn.cursor() as cur:
            cur.execute(sql_query)
            
            # Retrieve description to check if query returned rows (e.g. SELECT)
            if cur.description:
                colnames = [desc[0] for desc in cur.description]
                # Fetch up to 51 rows to detect truncation safely
                rows = cur.fetchmany(51)
                
                # Format output as a readable table string
                if not rows:
                    return "Query returned 0 rows."
                
                truncated = False
                if len(rows) > 50:
                    rows = rows[:50]
                    truncated = True
                
                result_str = " | ".join(colnames) + "\n"
                result_str += "-" * len(result_str) + "\n"
                for row in rows:
                    result_str += " | ".join(str(val) for val in row) + "\n"
                
                if truncated:
                    result_str += "... (results truncated to top 50 rows)\n"
                    
                return result_str.strip()
            else:
                return "Query executed successfully. No rows returned."
                
    except Exception as e:
        return f"Database Error: {str(e)}"
    finally:
        if conn:
            conn.close()
