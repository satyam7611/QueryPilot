import os
from typing import Type, TypeVar, Optional, List, Dict, Any
import litellm
from pydantic import BaseModel
from dotenv import load_dotenv

# Ensure environment is loaded from the correct workspace path
workspace_env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env")
load_dotenv(dotenv_path=workspace_env_path, override=True)

# Default model configuration
DEFAULT_MODEL = "gemini/gemini-3.5-flash"

T = TypeVar("T", bound=BaseModel)

def query_llm(
    messages: List[Dict[str, str]],
    model: str = DEFAULT_MODEL,
    temperature: float = 0.0,
    response_format: Optional[Type[T]] = None
) -> str | T:
    """
    Central gateway function to call LLMs via LiteLLM.
    Supports regular string responses and structured outputs via Pydantic schemas.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not configured in the environment.")
    
    # Configure safety settings if necessary, or pass kwargs
    import time
    max_retries = 5
    backoff = 4
    
    for attempt in range(max_retries):
        try:
            if response_format:
                # Call LiteLLM with Pydantic structured output format
                response = litellm.completion(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    response_format=response_format,
                    api_key=api_key
                )
                content = response.choices[0].message.content
                # Parse the content directly into the Pydantic class
                return response_format.model_validate_json(content)
            else:
                # Standard free-form call
                response = litellm.completion(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    api_key=api_key
                )
                return response.choices[0].message.content.strip()
                
        except Exception as e:
            err_str = str(e)
            # Catch 429, quota, or limit errors
            if "429" in err_str or "quota" in err_str.lower() or "limit" in err_str.lower():
                print(f"   [Gateway API Quota Limit] Sleeping {backoff} seconds before retry (Attempt {attempt+1}/{max_retries})...")
                time.sleep(backoff)
                backoff *= 2
            else:
                print(f"LLM Gateway Error calling {model}: {e}")
                raise e
                
    raise RuntimeError("Max retries exceeded for RateLimitError in LLM Gateway")

