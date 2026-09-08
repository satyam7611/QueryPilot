import time
import pytest
from app.core.cache import QueryResultCache, normalize_sql_for_cache
from app.agent.nodes.execute_sql import execute_sql
from unittest.mock import patch

def test_normalize_sql():
    sql1 = "SELECT  *   FROM   customers WHERE id = 1 ;"
    sql2 = "-- Comment\nSELECT * FROM customers WHERE id = 1"
    assert normalize_sql_for_cache(sql1) == normalize_sql_for_cache(sql2)

def test_cache_hit_and_miss():
    cache = QueryResultCache(default_ttl=60)
    sql = "SELECT COUNT(*) FROM customers;"
    
    # 1. Miss initially
    assert cache.get(None, "demo_v1", sql) is None
    
    # 2. Store result
    cache.set(None, "demo_v1", sql, "100")
    
    # 3. Hit
    assert cache.get(None, "demo_v1", sql) == "100"
    # Hit with different formatting
    assert cache.get(None, "demo_v1", "SELECT  COUNT(*)  FROM customers;\n") == "100"

def test_cache_dataset_isolation():
    cache = QueryResultCache(default_ttl=60)
    sql = "SELECT COUNT(*) FROM data;"
    
    cache.set("dataset_A", "hash_A", sql, "Result A")
    cache.set("dataset_B", "hash_B", sql, "Result B")
    
    assert cache.get("dataset_A", "hash_A", sql) == "Result A"
    assert cache.get("dataset_B", "hash_B", sql) == "Result B"
    assert cache.get(None, "demo_v1", sql) is None

def test_cache_schema_change_invalidation():
    cache = QueryResultCache(default_ttl=60)
    sql = "SELECT * FROM employees;"
    
    cache.set("ds_1", "hash_v1", sql, "Old Result")
    # Schema altered -> new hash_v2
    assert cache.get("ds_1", "hash_v2", sql) is None

def test_failed_query_not_cached():
    cache = QueryResultCache(default_ttl=60)
    sql = "SELECT * FROM nonexistent;"
    
    # Database Error strings must not be saved
    cache.set(None, "demo_v1", sql, "Database Error: table does not exist")
    assert cache.get(None, "demo_v1", sql) is None

def test_cache_ttl_expiration():
    cache = QueryResultCache(default_ttl=1)  # 1 second TTL
    sql = "SELECT 1;"
    cache.set(None, "demo_v1", sql, "1", ttl=1)
    
    assert cache.get(None, "demo_v1", sql) == "1"
    time.sleep(1.1)
    # Expired
    assert cache.get(None, "demo_v1", sql) is None

def test_dataset_invalidation():
    cache = QueryResultCache(default_ttl=60)
    cache.set("ds_to_del", "h1", "SELECT 1;", "res1")
    cache.set("ds_to_del", "h1", "SELECT 2;", "res2")
    cache.set("ds_keep", "h2", "SELECT 1;", "res_keep")
    
    cache.invalidate_dataset("ds_to_del")
    assert cache.get("ds_to_del", "h1", "SELECT 1;") is None
    assert cache.get("ds_to_del", "h1", "SELECT 2;") is None
    assert cache.get("ds_keep", "h2", "SELECT 1;") == "res_keep"

def test_execute_sql_node_caching_integration():
    from app.core.cache import query_cache
    from unittest.mock import MagicMock
    query_cache.clear()
    
    state = {
        "generated_sql": "SELECT 1 as num;",
        "dataset_id": "ds_integration",
        "schema_hash": "hash_int_1"
    }
    
    mock_tool = MagicMock()
    mock_tool.invoke.return_value = "num\n---\n1"
    
    with patch("app.agent.nodes.execute_sql.execute_readonly_sql", mock_tool):
        # First execution: Cache MISS -> invokes tool
        res1 = execute_sql(state)
        assert res1["is_cache_hit"] is False
        assert mock_tool.invoke.call_count == 1
        
        # Second execution: Cache HIT -> does NOT invoke tool again
        res2 = execute_sql(state)
        assert res2["is_cache_hit"] is True
        assert res2["query_result"] == "num\n---\n1"
        assert mock_tool.invoke.call_count == 1
