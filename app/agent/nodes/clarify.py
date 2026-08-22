from langgraph.types import interrupt
from app.agent.state import AgentState
from app.llm.gateway import query_llm
from app.prompts.clarification import CLARIFICATION_MERGE_SYSTEM_PROMPT, format_merge_prompt

def ask_clarification(state: AgentState) -> dict:
    """
    Pauses graph execution and waits for the user to select an option.
    Uses LangGraph's native interrupt mechanism.
    """
    print("\n[Node: ask_clarification] Pausing execution for user response...")
    
    # Trigger an interrupt, passing context to the runner (main.py)
    # The runner will capture this interrupt, ask the user, and resume with their answer
    user_choice = interrupt({
        "question": state.get("clarification_question"),
        "options": state.get("options")
    })
    
    return {
        "clarification_response": str(user_choice)
    }

def merge_clarification(state: AgentState) -> dict:
    """
    Takes the user's choice and merges it with the original question
    to create a single, clear, clarified intent query.
    """
    print("\n[Node: merge_clarification] Merging choice with original question...")
    
    original = state.get("original_question")
    options = state.get("options", [])
    response = state.get("clarification_response")
    
    # Resolve the selection (e.g. if user typed "1", map it to options[0])
    resolved_choice = response
    try:
        idx = int(response.strip()) - 1
        if 0 <= idx < len(options):
            resolved_choice = options[idx]
    except ValueError:
        # User typed raw text instead of a number, use it directly
        pass
        
    print(f" - Resolved choice: '{resolved_choice}'")
    
    # Construct the merge prompt
    prompt = format_merge_prompt(original, options, resolved_choice)
    messages = [
        {"role": "system", "content": CLARIFICATION_MERGE_SYSTEM_PROMPT},
        {"role": "user", "content": prompt}
    ]
    
    # Call LLM to merge
    clarified_intent = query_llm(messages=messages, temperature=0.0)
    print(f" - Clarified Intent: '{clarified_intent}'")
    
    return {
        "clarified_intent": clarified_intent,
        "is_ambiguous": False, # Mark as no longer ambiguous
    }
