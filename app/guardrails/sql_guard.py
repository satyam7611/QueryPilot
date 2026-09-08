import re

# Approved tables in our database schema
ALLOWED_TABLES = {"customers", "orders", "order_items", "products", "payments"}

# Forbidden keywords (write/ddl/admin operations)
FORBIDDEN_KEYWORDS = [
    r"\bDROP\b",
    r"\bDELETE\b",
    r"\bUPDATE\b",
    r"\bINSERT\b",
    r"\bTRUNCATE\b",
    r"\bALTER\b",
    r"\bCREATE\b",
    r"\bREPLACE\b",
    r"\bGRANT\b",
    r"\bREVOKE\b",
    r"\bEXECUTE\b",
    r"\bCOPY\b",
    r"\bVACUUM\b",
    r"\bCALL\b"
]

def is_safe_sql(sql_query: str, allowed_tables: set[str] = ALLOWED_TABLES) -> tuple[bool, str | None]:
    """
    Statically analyzes a SQL query for safety.
    Returns (True, None) if safe, or (False, "reason") if unsafe.
    """
    clean_query = sql_query.strip()
    
    # 1. Reject empty queries
    if not clean_query:
        return False, "SQL query is empty."
        
    # 2. Strip single-line comments (-- ...) and multi-line comments (/* ... */)
    no_comments = re.sub(r"--.*$", "", sql_query, flags=re.MULTILINE)
    no_comments = re.sub(r"/\*.*?\*/", "", no_comments, flags=re.DOTALL).strip()
    
    # Must begin with SELECT or WITH
    stripped_upper = no_comments.upper()
    if not (stripped_upper.startswith("SELECT") or stripped_upper.startswith("WITH")):
        return False, "Query must be a read-only SELECT or WITH statement."
        
    # 3. Check for multiple statements (SQL injection attempt via semicolons)
    statements = [s.strip() for s in no_comments.split(";") if s.strip()]
    if len(statements) > 1:
        return False, "Multiple SQL statements are not allowed (semicolon injection protection)."
        
    # 4. Check for forbidden keywords
    for keyword in FORBIDDEN_KEYWORDS:
        if re.search(keyword, no_comments, re.IGNORECASE):
            clean_kw = keyword.replace(r"\b", "")
            return False, f"Forbidden keyword detected in query: {clean_kw}."
            
    # 5. Check if referencing unauthorized tables (data exfiltration protection)
    # Identify Common Table Expressions (CTEs) so we don't falsely reject temp CTE table references
    ctes = set()
    cte_matches = re.findall(r"\b([a-zA-Z0-9_]+)\s+AS\s*\(", sql_query, re.IGNORECASE)
    for cte in cte_matches:
        ctes.add(cte.lower())
        
    local_allowed = allowed_tables.union(ctes)
    
    # Extract words that look like table references following FROM or JOIN
    matches = re.findall(r"\b(?:FROM|JOIN)\s+([a-zA-Z0-9_\"'\.]+)", sql_query, re.IGNORECASE)
    for table in matches:
        # Clean table name (remove quotes, schemas)
        clean_table = table.replace('"', '').replace("'", "").split('.')[-1].strip().lower()
        if clean_table and clean_table not in local_allowed:
            return False, f"Access denied to table: '{clean_table}'. Only business schema tables are allowed."
            
    return True, None
