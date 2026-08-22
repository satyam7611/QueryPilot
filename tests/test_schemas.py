import pytest
from pydantic import ValidationError
from app.schemas.outputs import QueryAnalysis, SQLGenerationResult

def test_query_analysis_valid():
    # Correct structure should validate successfully
    data = {
        "is_ambiguous": True,
        "is_out_of_domain": False,
        "intent": "Get best customer",
        "reasoning": "The term 'best customer' is vague.",
        "clarification_question": "How to define best customer?",
        "options": ["spending", "orders", "purchases"]
    }
    analysis = QueryAnalysis.model_validate(data)
    assert analysis.is_ambiguous is True
    assert analysis.is_out_of_domain is False
    assert len(analysis.options) == 3

def test_query_analysis_missing_required():
    # Missing required fields like 'is_ambiguous' should raise validation error
    data = {
        "intent": "Get best customer",
        "reasoning": "vague"
    }
    with pytest.raises(ValidationError):
        QueryAnalysis.model_validate(data)

def test_sql_generation_result_valid():
    # Valid SQL result
    data = {
        "sql": "SELECT * FROM customers;",
        "tables_used": ["customers"],
        "explanation": "Selects all customers."
    }
    result = SQLGenerationResult.model_validate(data)
    assert result.sql == "SELECT * FROM customers;"
    assert result.tables_used == ["customers"]
