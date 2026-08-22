import pytest
from app.guardrails.sql_guard import is_safe_sql

def test_safe_select_queries():
    # Standard read-only queries should pass
    safe_queries = [
        "SELECT * FROM customers;",
        "SELECT name, email FROM customers WHERE country = 'India';",
        "SELECT COUNT(*) FROM orders o JOIN payments p ON o.order_id = p.order_id;",
        "WITH sales AS (SELECT customer_id, SUM(total_amount) as total FROM orders GROUP BY customer_id) SELECT * FROM sales;",
        "SELECT name FROM products ORDER BY price DESC LIMIT 5"
    ]
    for query in safe_queries:
        is_safe, error = is_safe_sql(query)
        assert is_safe is True, f"Failed on safe query: {query}. Error: {error}"

def test_forbidden_keywords():
    # Destructive operations should be blocked
    unsafe_queries = [
        "DROP TABLE customers;",
        "DELETE FROM orders WHERE order_id = 1;",
        "UPDATE products SET price = 0 WHERE product_id = 2;",
        "INSERT INTO customers (name) VALUES ('Hacker');",
        "TRUNCATE TABLE payments;",
        "ALTER TABLE customers ADD COLUMN hack VARCHAR(10);"
    ]
    for query in unsafe_queries:
        is_safe, error = is_safe_sql(query)
        assert is_safe is False, f"Failed to block unsafe query: {query}"
        assert "Forbidden keyword detected" in error or "Query must be" in error

def test_semicolon_injection():
    # Multiple statements should be blocked
    queries = [
        "SELECT * FROM customers; DROP TABLE orders;",
        "SELECT * FROM products; DELETE FROM order_items;"
    ]
    for query in queries:
        is_safe, error = is_safe_sql(query)
        assert is_safe is False, f"Failed to block semicolon query: {query}"
        assert "Multiple SQL statements are not allowed" in error

def test_unauthorized_tables():
    # Queries attempting to query tables outside our schema should be blocked
    queries = [
        "SELECT * FROM users;",
        "SELECT * FROM customers JOIN user_accounts ON customers.customer_id = user_accounts.id;",
        "SELECT salary FROM employees;"
    ]
    for query in queries:
        is_safe, error = is_safe_sql(query)
        assert is_safe is False, f"Failed to block unauthorized table: {query}"
        assert "Access denied to table" in error
