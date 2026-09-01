import os
from app.agent.state import AgentState
from app.schemas.outputs import SQLGenerationResult
from app.llm.gateway import query_llm

SQL_SYSTEM_PROMPT = """
You are a PostgreSQL expert. Your task is to generate a valid, optimized, read-only SQL SELECT query based on the database schema provided and the user's question.

Database Schema:
{schema}

CRITICAL RULES:
1. Generate ONLY a read-only SELECT statement. DO NOT write INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE, or CREATE queries.
2. Ensure you join tables correctly using the foreign keys:
   - orders.customer_id joins with customers.customer_id
   - order_items.order_id joins with orders.order_id
   - order_items.product_id joins with products.product_id
   - payments.order_id joins with orders.order_id
3. Limit the results to 50 rows maximum unless explicitly requested otherwise.
4. Output your answer strictly matching the requested JSON structure.
"""

from langchain_core.runnables import RunnableConfig

SQL_SYSTEM_PROMPT_CUSTOM = """
You are a PostgreSQL expert. Your task is to generate a valid, optimized, read-only SQL SELECT query based on the database schema provided and the user's question.

Database Schema:
{schema}

CRITICAL RULES:
1. Generate ONLY a read-only SELECT statement. DO NOT write INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE, or CREATE queries.
2. Ensure you join tables correctly using any foreign keys defined in the DDL.
3. Limit the results to 50 rows maximum unless explicitly requested otherwise.
4. Output your answer strictly matching the requested JSON structure.
"""

def generate_sql(state: AgentState, config: RunnableConfig) -> dict:
    """
    Node that generates a PostgreSQL query from the question and schema.
    Supports self-correction loops by inspecting previous errors and SQL queries in the state.
    """
    # Use clarified_intent if we went through clarification, otherwise original_question
    query_text = state.get("clarified_intent") or state.get("original_question")
    schema = state.get("retrieved_schema")
    dataset_id = state.get("dataset_id")
    
    # Extract self-correction context
    previous_sql = state.get("generated_sql")
    previous_error = state.get("error")
    
    print(f"\n[Node: generate_sql] Generating SQL for: '{query_text}'...")
    
    # Select prompt template based on dataset context
    if dataset_id:
        sys_prompt = SQL_SYSTEM_PROMPT_CUSTOM.format(schema=schema)
    else:
        sys_prompt = SQL_SYSTEM_PROMPT.format(schema=schema)
        
    user_prompt = f"Write a SQL query for the question: {query_text}"
    
    # If this is a retry attempt, inject error feedback
    if previous_sql and previous_error:
        print(f" - Self-Correction Triggered! Repairing query due to: {previous_error}")
        user_prompt += f"\n\n--- PREVIOUS ERROR FEEDBACK ---\n"
        user_prompt += f"Your previous SQL query: {previous_sql}\n"
        user_prompt += f"Validation / Compilation Error: {previous_error}\n"
        user_prompt += "Please identify the bug (e.g. wrong column names, incorrect join keys, invalid syntax), fix it, and generate a corrected SQL query."
        user_prompt += "\n--------------------------------\n"
        
    messages = [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": user_prompt}
    ]
    
    # Extract request-scoped api key
    api_key = config.get("configurable", {}).get("api_key")
    
    try:
        # Call LLM with Structured Output Pydantic schema
        result: SQLGenerationResult = query_llm(
            messages=messages,
            response_format=SQLGenerationResult,
            temperature=0.0,
            api_key=api_key
        )
        
        print(f" - Generated SQL: {result.sql}")
        print(f" - Tables Used: {result.tables_used}")
        
        return {
            "generated_sql": result.sql,
            "explanation": result.explanation,
            "tables_used": result.tables_used
        }
        
    except Exception as e:
        print(f"Error in generate_sql node: {e}")
        raise e
