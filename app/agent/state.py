from typing import TypedDict, Optional, List, Dict, Any

class AgentState(TypedDict):
    """
    State definition for the Text-to-SQL LangGraph workflow.
    This state object is passed from node to node, accumulating execution details.
    """
    # Inputs & History
    original_question: str
    conversation_history: List[Dict[str, str]]  # list of {"role": "...", "content": "..."}
    visited_nodes: List[str]
    
    
    # Analysis outputs
    is_ambiguous: bool
    is_out_of_domain: bool
    clarification_question: Optional[str]
    options: Optional[List[str]]
    
    # Clarification interactions
    clarification_response: Optional[str]
    clarified_intent: Optional[str]
    
    # RAG & Generation
    retrieved_schema: Optional[str]
    generated_sql: Optional[str]
    explanation: Optional[str]
    tables_used: Optional[List[str]]
    
    # Execution & Recovery
    validation_result: Optional[bool]
    query_result: Optional[Any]  # Can be list of rows, columns, or status string
    error: Optional[str]
    retry_count: int
    
    # Final Output
    final_answer: Optional[str]
    
    # Dataset Context
    dataset_id: Optional[str]
