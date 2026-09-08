from app.agent.state import AgentState
from app.schemas.outputs import QueryAnalysis
from app.llm.gateway import query_llm
from app.prompts.analyzer import ANALYZER_SYSTEM_PROMPT, ANALYZER_SYSTEM_PROMPT_TEMPLATE

from langchain_core.runnables import RunnableConfig

def analyze_question(state: AgentState, config: RunnableConfig) -> dict:
    """
    Node that analyzes the user's natural language question.
    Determines if clarification is required or if it is out-of-scope.
    """
    question = state.get("original_question")
    dataset_id = state.get("dataset_id")
    print(f"\n[Node: analyze_question] Analyzing: '{question}'...")
    
    if dataset_id:
        from app.services.dataset_service import get_dataset_ddl
        try:
            schema_info = get_dataset_ddl(dataset_id)
            sys_prompt = ANALYZER_SYSTEM_PROMPT_TEMPLATE.format(schema_info=schema_info)
        except Exception as e:
            print(f"Error loading schema info for analysis: {e}")
            sys_prompt = ANALYZER_SYSTEM_PROMPT
    else:
        sys_prompt = ANALYZER_SYSTEM_PROMPT
        
    messages = [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": f"Analyze the user question: {question}"}
    ]
    
    # Extract request-scoped api key
    api_key = config.get("configurable", {}).get("api_key")
    
    try:
        # Call LLM via Gateway with Structured Output Pydantic schema
        analysis: QueryAnalysis = query_llm(
            messages=messages,
            response_format=QueryAnalysis,
            temperature=0.0,
            api_key=api_key
        )
        
        print(f" - Ambiguous: {analysis.is_ambiguous}")
        print(f" - Out-of-Domain: {analysis.is_out_of_domain}")
        print(f" - Reasoning: {analysis.reasoning}")
        
        # Return state updates
        return {
            "is_ambiguous": analysis.is_ambiguous,
            "is_out_of_domain": analysis.is_out_of_domain,
            "clarification_question": analysis.clarification_question,
            "options": analysis.options,
            "intent": analysis.intent
        }
        
    except Exception as e:
        print(f"Error in analyze_question node: {e}")
        raise e
