import os
from langchain_core.tools import tool
from psycopg import connect
from dotenv import load_dotenv

# Load env variables explicitly
workspace_env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env")
load_dotenv(dotenv_path=workspace_env_path)

@tool
def execute_readonly_sql(sql_query: str) -> str:
    """
    Executes a read-only SELECT SQL query against the PostgreSQL database.
    Input must be a valid, read-only SQL SELECT statement.
    Returns the columns and rows as a formatted string, or an error message.
    """
    # Connection parameters
    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "5432")
    user = os.getenv("DB_USER", "postgres")
    password = os.getenv("DB_PASSWORD")
    dbname = os.getenv("DB_NAME", "querypilot")
    
    conn = None
    try:
        conn = connect(
            host=host,
            port=port,
            user=user,
            password=password,
            dbname=dbname
        )
        with conn.cursor() as cur:
            cur.execute(sql_query)
            
            # Retrieve description to check if query returned rows (e.g. SELECT)
            if cur.description:
                colnames = [desc[0] for desc in cur.description]
                rows = cur.fetchall()
                
                # Format output as a readable table string
                if not rows:
                    return "Query returned 0 rows."
                
                result_str = " | ".join(colnames) + "\n"
                result_str += "-" * len(result_str) + "\n"
                for row in rows:
                    result_str += " | ".join(str(val) for val in row) + "\n"
                return result_str.strip()
            else:
                conn.commit()
                return "Query executed successfully. No rows returned."
                
    except Exception as e:
        return f"Database Error: {str(e)}"
    finally:
        if conn:
            conn.close()
