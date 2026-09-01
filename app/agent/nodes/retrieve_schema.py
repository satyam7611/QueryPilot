from app.agent.state import AgentState
from app.rag.retriever import retrieve_relevant_schema

from langchain_core.runnables import RunnableConfig
from app.rag.retriever import retrieve_relevant_schema

def retrieve_schema(state: AgentState, config: RunnableConfig) -> dict:
    """
    Node that retrieves the database schema mapping.
    Uses semantic Schema RAG for default DB, or retrieves custom schema dynamically.
    """
    dataset_id = state.get("dataset_id")
    api_key = config.get("configurable", {}).get("api_key")
    
    if dataset_id:
        print(f"\n[Node: retrieve_schema] Dynamically loading custom schema for dataset: {dataset_id}...")
        # Import dynamically to avoid circular dependencies
        from app.services.dataset_service import get_dataset_ddl
        try:
            retrieved = get_dataset_ddl(dataset_id)
        except Exception as e:
            print(f"Error loading custom schema: {e}")
            retrieved = f"-- Error loading schema for dataset {dataset_id}: {str(e)}"
    else:
        # Use clarified_intent if we went through clarification, otherwise original_question
        query_text = state.get("clarified_intent") or state.get("original_question")
        print(f"\n[Node: retrieve_schema] Searching Schema RAG for: '{query_text}'...")
        # Retrieve top 3 most relevant table schemas semantically
        retrieved = retrieve_relevant_schema(query_text, k=3, api_key=api_key)
    
    return {
        "retrieved_schema": retrieved
    }
