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

def generate_answer(state: AgentState) -> dict:
    """
    Node that synthesizes a natural language answer from the database result and the user's question.
    """
    print("\n[Node: generate_answer] Synthesizing final answer...")
    
    question = state.get("clarified_intent") or state.get("original_question")
    results = state.get("query_result")
    error = state.get("error")
    
    # If we had a persistent execution error
    if error and not results:
        return {
            "final_answer": f"I'm sorry, I encountered a database error while trying to run your query: {error}"
        }
        
    messages = [
        {"role": "system", "content": ANSWER_SYSTEM_PROMPT.format(question=question, results=str(results))},
        {"role": "user", "content": "Generate the final answer."}
    ]
    
    try:
        final_answer = query_llm(messages=messages, temperature=0.0)
        print(f" - Final Answer: '{final_answer}'")
        return {
            "final_answer": final_answer
        }
    except Exception as e:
        print(f"Error in generate_answer node: {e}")
        return {
            "final_answer": f"Failed to generate answer. Database output: {results}"
        }
