import pytest
import json
from unittest.mock import patch, MagicMock
from app.rag.retriever import SchemaRetriever, retrieve_relevant_schema, get_schema_retriever
from app.rag.schema_docs import build_custom_schema_card, SCHEMA_CARDS

def test_build_custom_schema_card():
    dataset_id = "test-dataset-1"
    table_name = "dataset_test_1"
    filename = "employees.csv"
    columns_meta = [
        ("Employee ID", "employee_id", "INTEGER"),
        ("Full Name", "full_name", "VARCHAR(255)"),
        ("Salary", "salary", "DECIMAL(18, 4)"),
        ("Joining Date", "joining_date", "DATE")
    ]
    card = build_custom_schema_card(dataset_id, table_name, filename, columns_meta)
    
    assert card["dataset_id"] == dataset_id
    assert card["table_name"] == table_name
    assert "CREATE TABLE dataset_test_1" in card["ddl"]
    assert '"employee_id" INTEGER' in card["ddl"]
    assert '"salary" DECIMAL(18, 4)' in card["ddl"]
    assert "schema_hash" in card
    assert len(card["schema_hash"]) == 16
    assert "Dataset: employees.csv" in card["text_to_embed"]

def test_dataset_schema_hash_consistency_and_change():
    cols1 = [("id", "id", "INTEGER"), ("name", "name", "VARCHAR(255)")]
    cols2 = [("id", "id", "INTEGER"), ("name", "name", "VARCHAR(255)")]
    cols_changed = [("id", "id", "INTEGER"), ("name", "name", "VARCHAR(255)"), ("role", "role", "VARCHAR(255)")]
    
    card1 = build_custom_schema_card("d1", "t1", "test.csv", cols1)
    card2 = build_custom_schema_card("d1", "t1", "test.csv", cols2)
    card3 = build_custom_schema_card("d1", "t1", "test.csv", cols_changed)
    
    assert card1["schema_hash"] == card2["schema_hash"]
    assert card1["schema_hash"] != card3["schema_hash"]

def test_dataset_indexing_and_unchanged_reuse():
    retriever = SchemaRetriever()
    fake_vector = [0.1] * 768
    
    with patch("app.rag.retriever.get_embedding", return_value=fake_vector) as mock_embed:
        cols = [("col_a", "col_a", "INTEGER"), ("col_b", "col_b", "VARCHAR(255)")]
        
        # 1. First index call should generate embedding
        res1 = retriever.index_dataset("ds_100", "table_100", "data.csv", cols)
        assert mock_embed.call_count == 1
        assert res1["embedding"] == fake_vector
        
        # 2. Re-indexing identical schema should reuse existing embedding without calling get_embedding again
        res2 = retriever.index_dataset("ds_100", "table_100", "data.csv", cols)
        assert mock_embed.call_count == 1  # Not incremented!
        assert res2["schema_hash"] == res1["schema_hash"]

def test_dataset_schema_change_regeneration():
    retriever = SchemaRetriever()
    fake_vector1 = [0.1] * 768
    fake_vector2 = [0.2] * 768
    
    with patch("app.rag.retriever.get_embedding", side_effect=[fake_vector1, fake_vector2]) as mock_embed:
        cols1 = [("col_a", "col_a", "INTEGER")]
        res1 = retriever.index_dataset("ds_200", "table_200", "data.csv", cols1)
        assert res1["embedding"] == fake_vector1
        assert mock_embed.call_count == 1
        
        # Schema updated with new column -> embedding must regenerate
        cols2 = [("col_a", "col_a", "INTEGER"), ("col_b", "col_b", "DECIMAL(18, 4)")]
        res2 = retriever.index_dataset("ds_200", "table_200", "data.csv", cols2)
        assert res2["embedding"] == fake_vector2
        assert mock_embed.call_count == 2
        assert res2["schema_hash"] != res1["schema_hash"]

def test_dataset_isolation():
    retriever = SchemaRetriever()
    vec_a = [1.0, 0.0, 0.0]
    vec_b = [0.0, 1.0, 0.0]
    query_vec = [1.0, 0.0, 0.0]
    
    with patch("app.rag.retriever.get_embedding", side_effect=[vec_a, vec_b, query_vec]):
        # Index Dataset A
        retriever.index_dataset("dataset_A", "table_A", "users_A.csv", [("user_id", "user_id", "INTEGER")])
        # Index Dataset B
        retriever.index_dataset("dataset_B", "table_B", "orders_B.csv", [("order_id", "order_id", "INTEGER")])
        
        # Querying with dataset_id="dataset_A" must return table_A DDL ONLY and never table_B
        retrieved_a = retriever.retrieve("Show all users", dataset_id="dataset_A")
        assert "table_A" in retrieved_a
        assert "table_B" not in retrieved_a
        assert "customers" not in retrieved_a

def test_demo_db_retrieval_intact():
    query_vec = [0.1] * 768
    with patch("app.rag.retriever.get_embedding", return_value=query_vec):
        # Demo retrieval (dataset_id=None) returns demo tables
        retrieved = retrieve_relevant_schema("What are the best selling products?", k=2, dataset_id=None)
        assert "-- Table:" in retrieved
        assert "CREATE TABLE" in retrieved
        # Must not have custom table references
        assert "dataset_" not in retrieved

def test_delete_dataset_cleanup():
    retriever = SchemaRetriever()
    fake_vector = [0.1] * 768
    with patch("app.rag.retriever.get_embedding", return_value=fake_vector):
        retriever.index_dataset("ds_del", "table_del", "file.csv", [("id", "id", "INTEGER")])
        assert "ds_del" in retriever.dataset_cache
        
        retriever.delete_dataset("ds_del")
        assert "ds_del" not in retriever.dataset_cache
