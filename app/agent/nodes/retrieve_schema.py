from app.agent.state import AgentState
from app.rag.retriever import retrieve_relevant_schema, get_active_schema_hash
from langchain_core.runnables import RunnableConfig

def retrieve_schema(state: AgentState, config: RunnableConfig) -> dict:
    """
    Node that retrieves the database schema mapping via Schema RAG.
    Retrieves semantic schema cards for the demo database or isolated custom datasets.
    """
    dataset_id = state.get("dataset_id")
    api_key = config.get("configurable", {}).get("api_key")
    
    # Use clarified_intent if we went through clarification, otherwise original_question
    query_text = state.get("clarified_intent") or state.get("original_question")
    print(f"\n[Node: retrieve_schema] Searching Schema RAG for: '{query_text}' (dataset: {dataset_id or 'demo'})...")
    
    schema_hash = get_active_schema_hash(dataset_id)
    try:
        retrieved = retrieve_relevant_schema(query_text, k=3, api_key=api_key, dataset_id=dataset_id)
    except Exception as e:
        print(f"Error in retrieve_schema node: {e}")
        retrieved = f"-- Error retrieving schema: {str(e)}"
    
    return {
        "retrieved_schema": retrieved,
        "schema_hash": schema_hash
    }
