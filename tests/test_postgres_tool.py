import pytest
from app.tools.postgres_tool import execute_readonly_sql

def test_tool_select_one():
    # Verify that a simple SELECT 1 executes and returns the correct formatted string
    result = execute_readonly_sql.invoke({"sql_query": "SELECT 1 as num;"})
    assert "Database Error" not in result
    assert "num" in result
    assert "1" in result

def test_tool_syntax_error():
    # Verify that the tool catches syntax errors and outputs a Database Error string
    result = execute_readonly_sql.invoke({"sql_query": "SELECT * FROM non_existent_table;"})
    assert result.startswith("Database Error")
    assert "relation \"non_existent_table\" does not exist" in result.lower()
