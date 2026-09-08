from app.agent.state import AgentState
from app.llm.gateway import query_llm

ANSWER_SYSTEM_PROMPT = """
You are a friendly customer service and business intelligence assistant. Your task is to take a user's question and the raw PostgreSQL database results, and synthesize a clear, helpful, natural language answer.

Context:
User Question: {question}
Database Query Results:
{results}

CRITICAL RULES:
1. Provide a direct, polite, and accurate response based *only* on the database results.
2. If there are prices or amounts, format them nicely (e.g. ₹84,250 or $1,200).
3. Do not invent details not present in the results.
4. Keep the answer concise and business-focused.
"""

from langchain_core.runnables import RunnableConfig

def generate_answer(state: AgentState, config: RunnableConfig) -> dict:
    """
    Node that synthesizes a natural language answer from the database result and the user's question.
    """
    print("\n[Node: generate_answer] Synthesizing final answer...")
    
    question = state.get("clarified_intent") or state.get("original_question")
    results = state.get("query_result")
    error = state.get("error")
    validation_result = state.get("validation_result")
    
    # If the query failed validation or execution, or if we have no valid query_result
    if (error and not results) or validation_result is False or results is None:
        err_msg = error or "The query could not be validated or executed safely."
        return {
            "final_answer": f"I'm sorry, your query could not be completed: {err_msg}"
        }
        
    messages = [
        {"role": "system", "content": ANSWER_SYSTEM_PROMPT.format(question=question, results=str(results))},
        {"role": "user", "content": "Generate the final answer."}
    ]
    
    # Extract request-scoped api key
    api_key = config.get("configurable", {}).get("api_key")
    
    try:
        final_answer = query_llm(messages=messages, temperature=0.0, api_key=api_key)
        print(f" - Final Answer: '{final_answer}'")
        return {
            "final_answer": final_answer
        }
    except Exception as e:
        print(f"Error in generate_answer node: {e}")
        raise e
