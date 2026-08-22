from app.agent.state import AgentState
from app.rag.retriever import retrieve_relevant_schema

def retrieve_schema(state: AgentState) -> dict:
    """
    Node that retrieves the database schema mapping.
    Uses semantic Schema RAG to fetch the top 3 most relevant table cards.
    """
    # Use clarified_intent if we went through clarification, otherwise original_question
    query_text = state.get("clarified_intent") or state.get("original_question")
    print(f"\n[Node: retrieve_schema] Searching Schema RAG for: '{query_text}'...")
    
    # Retrieve top 3 most relevant table schemas semantically
    retrieved = retrieve_relevant_schema(query_text, k=3)
    
    return {
        "retrieved_schema": retrieved
    }
