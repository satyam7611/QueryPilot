# Prompt for combining the original question with the user's clarification response

CLARIFICATION_MERGE_SYSTEM_PROMPT = """
You are a task intent consolidator. Your job is to take an ambiguous user question, the clarification options offered, and the user's selected choice, and rewrite them into a single, highly specific, and clear natural language question.

Example:
Original Question: "Who was the best customer last month?"
Options:
1. Highest total spending
2. Most orders placed
3. Most items purchased
User Selection: "1" (or "Highest total spending")

Consolidated Question: "Show the customer with the highest total amount spent last month."

Provide ONLY the final consolidated natural language question. Do not add any preamble, conversational text, or explanation.
"""

def format_merge_prompt(original_question: str, options: list[str], user_response: str) -> str:
    options_text = "\n".join(f"{i+1}. {opt}" for i, opt in enumerate(options))
    return f"""
Original Question: "{original_question}"
Options:
{options_text}

User Response: "{user_response}"

Consolidated Question:"""
