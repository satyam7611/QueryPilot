import os
import json
import pytest
from fastapi.testclient import TestClient
from app.web_main import app
from app.services.dataset_service import ensure_metadata_table, get_db_connection

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_metadata_db():
    """Fixture ensuring datasets_metadata table is prepared before tests run."""
    ensure_metadata_table()

def test_health_check():
    """Verifies that the GET /health check endpoint functions correctly."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}

def test_upload_invalid_extension():
    """Verifies that non-CSV/non-XLSX file uploads are rejected with code 400."""
    files = {"file": ("test.txt", b"plain text content", "text/plain")}
    response = client.post("/api/datasets/upload", files=files)
    assert response.status_code == 400
    assert "Only CSV and XLSX" in response.json()["detail"]

def test_upload_empty_file():
    """Verifies that empty file uploads are rejected with code 400."""
    files = {"file": ("empty.csv", b"", "text/csv")}
    response = client.post("/api/datasets/upload", files=files)
    assert response.status_code == 400
    assert "empty" in response.json()["detail"].lower()

def test_upload_valid_csv():
    """Verifies successful upload, parsing, table creation, and metadata seeding of a valid CSV."""
    csv_data = (
        "id,name,value\n"
        "1,Alice,10.5\n"
        "2,Bob,20.0\n"
    )
    files = {"file": ("users.csv", csv_data.encode("utf-8"), "text/csv")}
    response = client.post("/api/datasets/upload", files=files)
    assert response.status_code == 200
    
    res_data = response.json()
    assert res_data["status"] == "success"
    assert "dataset_id" in res_data
    dataset_id = res_data["dataset_id"]
    
    # 1. Fetch Dynamic Schema DDL
    schema_res = client.get(f"/api/datasets/{dataset_id}/schema")
    assert schema_res.status_code == 200
    ddl = schema_res.json()["ddl"]
    assert "CREATE TABLE" in ddl
    assert "id INTEGER" in ddl
    assert "value DECIMAL" in ddl
    
    # 2. Cleanup dataset
    delete_res = client.delete(f"/api/datasets/{dataset_id}")
    assert delete_res.status_code == 200
    assert delete_res.json()["status"] == "success"

def test_query_out_of_domain():
    """Verifies that out-of-domain queries (e.g. DROP TABLE) are rejected by the analyzer."""
    from unittest.mock import patch
    from app.schemas.outputs import QueryAnalysis
    
    mock_analysis = QueryAnalysis(
        is_ambiguous=False,
        is_out_of_domain=True,
        clarification_question=None,
        options=None,
        intent="DROP TABLE customers;",
        reasoning="Attempted table deletion is out of database query scope."
    )
    
    with patch("app.agent.nodes.analyze.query_llm", return_value=mock_analysis):
        payload = {
            "question": "DROP TABLE customers;",
            "dataset_id": None,
            "api_key": None
        }
        response = client.post("/api/query", json=payload)
        assert response.status_code == 200
        
        res_data = response.json()
        assert res_data["status"] == "completed"
        assert "Query rejected" in res_data["final_answer"]
        assert "Destructive SQL operations" in res_data["final_answer"]

def test_query_guardrails_block_custom_dataset():
    """Verifies that dynamic guardrails prevent a custom dataset from querying unauthorized tables."""
    from app.agent.nodes.validate_sql import validate_sql
    from app.services.dataset_service import process_and_save_dataset, delete_user_dataset
    
    # 1. Create a dummy dataset
    csv_data = "id,name\n1,Test\n"
    dataset_id = process_and_save_dataset(
        file_bytes=csv_data.encode("utf-8"),
        filename="dummy.csv",
        session_id="test-session"
    )
    
    try:
        # 2. Mock state referencing unauthorized "customers" table
        state = {
            "generated_sql": "SELECT * FROM customers;",
            "retry_count": 0,
            "dataset_id": dataset_id
        }
        
        # Run node function directly
        result = validate_sql(state)
        
        # Validation must fail
        assert result["validation_result"] is False
        assert "Guardrail Rejection" in result["error"]
        assert "Access denied to table: 'customers'" in result["error"]
    finally:
        # Cleanup table
        delete_user_dataset(dataset_id, "test-session")
