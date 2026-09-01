from app.agent.state import AgentState

import re

def handle_out_of_domain(state: AgentState) -> dict:
    """
    Node that handles questions classified as out-of-domain.
    Friendly rejects the query and ends the graph execution.
    """
    print("\n[Node: handle_out_of_domain] Rejecting query as out-of-domain...")
    question = state.get("original_question") or ""
    
    # Check if the query attempts destructive SQL operations directly
    destructive_keywords = ["DROP", "DELETE", "UPDATE", "INSERT", "TRUNCATE", "ALTER", "CREATE", "GRANT", "REVOKE"]
    blocked_op = None
    for kw in destructive_keywords:
        if re.search(r"\b" + kw + r"\b", question, re.IGNORECASE):
            blocked_op = kw
            break
            
    if blocked_op:
        rejection_msg = (
            f"❌ Query rejected\n\n"
            f"Reason:\n"
            f"Destructive SQL operations are not allowed.\n\n"
            f"Allowed:\n"
            f"SELECT / WITH queries only.\n\n"
            f"Blocked operation:\n"
            f"{blocked_op}"
        )
    else:
        rejection_msg = (
            f"I'm sorry, but I can only help you query data inside our database schema "
            f"(customers, orders, order items, products, and payments). "
            f"The question '{question}' is outside my business domain."
        )
        
    return {
        "final_answer": rejection_msg
    }
