from pydantic import BaseModel, Field
from typing import Optional, List

class QueryAnalysis(BaseModel):
    """
    Structured output schema for initial analysis of the user's natural language question.
    Determines if the query is clear, ambiguous, or out-of-domain.
    """
    is_ambiguous: bool = Field(
        description="True if the question has multiple valid interpretations in the context of our database (e.g., 'best customer', 'top products')."
    )
    is_out_of_domain: bool = Field(
        description="True if the question cannot be answered by our database (e.g., weather, general knowledge, math operations unrelated to business data)."
    )
    intent: str = Field(
        description="A brief description of what the user is trying to find out."
    )
    reasoning: str = Field(
        description="Step-by-step reasoning behind classifying this question as ambiguous, clear, or out-of-domain."
    )
    clarification_question: Optional[str] = Field(
        default=None,
        description="If is_ambiguous is True, this should be a polite question asking for clarification (e.g. 'How would you like to define the best customer?')."
    )
    options: Optional[List[str]] = Field(
        default=None,
        description="If is_ambiguous is True, provide 3 distinct, clear choices for the user (e.g., ['Highest total spending', 'Most orders placed', 'Highest average order value'])."
    )

class SQLGenerationResult(BaseModel):
    """
    Structured output schema for the SQL generation model.
    Forces the LLM to separate the raw query from explanation and metadata.
    """
    sql: str = Field(
        description="The raw, valid PostgreSQL query that can be executed directly."
    )
    tables_used: List[str] = Field(
        description="List of tables (e.g., ['customers', 'orders']) referenced in the generated SQL."
    )
    explanation: str = Field(
        description="A brief explanation of how the query works and what columns/joins it uses."
    )
