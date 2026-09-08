import pytest
from app.guardrails.sql_guard import is_safe_sql
from app.tools.postgres_tool import execute_readonly_sql, get_readonly_db_connection

def test_destructive_ddl_blocked():
    attacks = [
        "DROP TABLE customers;",
        "DROP TABLE IF EXISTS orders CASCADE;",
        "TRUNCATE payments;",
        "ALTER TABLE products DROP COLUMN price;",
        "CREATE TABLE backdoor (id INT);"
    ]
    for sql in attacks:
        safe, error = is_safe_sql(sql)
        assert safe is False
        assert "Forbidden keyword detected" in error or "Query must be" in error

def test_destructive_dml_blocked():
    attacks = [
        "DELETE FROM customers WHERE customer_id = 1;",
        "UPDATE products SET price = 0;",
        "INSERT INTO customers (name, email) VALUES ('hacker', 'hacker@evil.com');",
        "INSERT INTO payments (amount) VALUES (999999);"
    ]
    for sql in attacks:
        safe, error = is_safe_sql(sql)
        assert safe is False
        assert "Forbidden keyword detected" in error or "Query must be" in error

def test_comment_and_stacked_injection_blocked():
    attacks = [
        "/* comment */ SELECT * FROM customers; DROP TABLE orders;",
        "SELECT * FROM customers /* inline comment */ ; DELETE FROM orders;",
        "WITH cte AS (SELECT 1) SELECT * FROM cte; DROP TABLE payments;"
    ]
    for sql in attacks:
        safe, error = is_safe_sql(sql)
        assert safe is False
        assert "Multiple SQL statements" in error or "Forbidden keyword" in error

def test_unauthorized_and_cross_dataset_tables_blocked():
    # Attempting to access other tables
    safe, error = is_safe_sql("SELECT * FROM pg_shadow;")
    assert safe is False
    assert "Access denied to table: 'pg_shadow'" in error
    
    # Custom dataset allowlist strictly enforced
    safe_ds, error_ds = is_safe_sql("SELECT * FROM customers;", allowed_tables={"dataset_abc_123"})
    assert safe_ds is False
    assert "Access denied to table: 'customers'" in error_ds

def test_admin_commands_blocked():
    attacks = [
        "GRANT ALL PRIVILEGES ON DATABASE querypilot TO public;",
        "REVOKE SELECT ON customers FROM postgres;",
        "COPY customers TO '/tmp/data.csv';",
        "CALL some_proc();"
    ]
    for sql in attacks:
        safe, error = is_safe_sql(sql)
        assert safe is False

def test_database_level_readonly_enforcement():
    """
    Verifies defense in depth: even if an INSERT/UPDATE statement bypasses application
    validation and is sent to the read-only connection, PostgreSQL rejects it at the DB level.
    """
    conn = get_readonly_db_connection()
    try:
        with conn.cursor() as cur:
            with pytest.raises(Exception) as excinfo:
                cur.execute("INSERT INTO customers (name, email, signup_date, country) VALUES ('Test', 't@t.com', '2026-01-01', 'US');")
            assert "read-only" in str(excinfo.value).lower() or "transaction" in str(excinfo.value).lower()
    finally:
        conn.close()

def test_database_level_drop_rejected():
    """
    Verifies that DROP TABLE is rejected at DB transaction level on the read-only connection.
    """
    conn = get_readonly_db_connection()
    try:
        with conn.cursor() as cur:
            with pytest.raises(Exception) as excinfo:
                cur.execute("DROP TABLE IF EXISTS dummy_test_table;")
            assert "read-only" in str(excinfo.value).lower() or "transaction" in str(excinfo.value).lower()
    finally:
        conn.close()
