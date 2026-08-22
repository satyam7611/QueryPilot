import re

# Approved tables in our database schema
ALLOWED_TABLES = {"customers", "orders", "order_items", "products", "payments"}

# Forbidden keywords (write/ddl operations)
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
    r"\bREVOKE\b"
]

def is_safe_sql(sql_query: str) -> tuple[bool, str | None]:
    """
    Statically analyzes a SQL query for safety.
    Returns (True, None) if safe, or (False, "reason") if unsafe.
    """
    clean_query = sql_query.strip().upper()
    
    # 1. Reject empty queries
    if not clean_query:
        return False, "SQL query is empty."
        
    # 2. Must begin with SELECT (or WITH for CTEs)
    # Remove leading comments and whitespace
    stripped_query = re.sub(r"^--.*$", "", sql_query, flags=re.MULTILINE).strip().upper()
    if not (stripped_query.startswith("SELECT") or stripped_query.startswith("WITH")):
        return False, "Query must be a read-only SELECT or WITH statement."
        
    # 3. Check for multiple statements (SQL injection attempt via semicolons)
    # Split by semicolon and verify there are no commands after it
    statements = [s.strip() for s in sql_query.split(";") if s.strip()]
    if len(statements) > 1:
        return False, "Multiple SQL statements are not allowed (semicolon injection protection)."
        
    # 4. Check for forbidden keywords
    for keyword in FORBIDDEN_KEYWORDS:
        if re.search(keyword, clean_query, re.IGNORECASE):
            return False, f"Forbidden keyword detected in query: {keyword.replace(r'\\b', '')}."
            
    # 5. Check if referencing unauthorized tables (data exfiltration protection)
    # Identify Common Table Expressions (CTEs) so we don't falsely reject temp CTE table references
    ctes = set()
    cte_matches = re.findall(r"\b([a-zA-Z0-9_]+)\s+AS\s*\(", sql_query, re.IGNORECASE)
    for cte in cte_matches:
        ctes.add(cte.lower())
        
    local_allowed = ALLOWED_TABLES.union(ctes)
    
    # Extract words that look like table references following FROM or JOIN
    matches = re.findall(r"\b(?:FROM|JOIN)\s+([a-zA-Z0-9_\"'\.]+)", sql_query, re.IGNORECASE)
    for table in matches:
        # Clean table name (remove quotes, schemas)
        clean_table = table.replace('"', '').replace("'", "").split('.')[-1].strip().lower()
        if clean_table and clean_table not in local_allowed:
            return False, f"Access denied to table: '{clean_table}'. Only business schema tables are allowed."
            
    return True, None
