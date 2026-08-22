from app.agent.state import AgentState
from app.schemas.outputs import QueryAnalysis
from app.llm.gateway import query_llm
from app.prompts.analyzer import ANALYZER_SYSTEM_PROMPT

def analyze_question(state: AgentState) -> dict:
    """
    Node that analyzes the user's natural language question.
    Determines if clarification is required or if it is out-of-scope.
    """
    question = state.get("original_question")
    print(f"\n[Node: analyze_question] Analyzing: '{question}'...")
    
    messages = [
        {"role": "system", "content": ANALYZER_SYSTEM_PROMPT},
        {"role": "user", "content": f"Analyze the user question: {question}"}
    ]
    
    try:
        # Call LLM via Gateway with Structured Output Pydantic schema
        analysis: QueryAnalysis = query_llm(
            messages=messages,
            response_format=QueryAnalysis,
            temperature=0.0
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
        # Graceful fallback: treat as clear but log the error
        return {
            "is_ambiguous": False,
            "is_out_of_domain": False,
            "intent": question,
            "error": f"Analysis node failure: {str(e)}"
        }
