from app.agent.state import AgentState

def handle_out_of_domain(state: AgentState) -> dict:
    """
    Node that handles questions classified as out-of-domain.
    Friendly rejects the query and ends the graph execution.
    """
    print("\n[Node: handle_out_of_domain] Rejecting query as out-of-domain...")
    question = state.get("original_question")
    rejection_msg = (
        f"I'm sorry, but I can only help you query data inside our database schema "
        f"(customers, orders, order items, products, and payments). "
        f"The question '{question}' is outside my business domain."
    )
    return {
        "final_answer": rejection_msg
    }
