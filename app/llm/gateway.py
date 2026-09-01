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
    response_format: Optional[Type[T]] = None,
    api_key: Optional[str] = None
) -> str | T:
    """
    Central gateway function to call LLMs via LiteLLM.
    Supports regular string responses and structured outputs via Pydantic schemas.
    """
    active_key = api_key or os.getenv("GEMINI_API_KEY")
    if not active_key:
        raise ValueError("GEMINI_API_KEY is not configured in the environment.")
    
    # Configure safety settings if necessary, or pass kwargs
    import time
    max_retries = 2
    backoff = 2
    
    for attempt in range(max_retries):
        try:
            if response_format:
                # Call LiteLLM with Pydantic structured output format
                response = litellm.completion(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    response_format=response_format,
                    api_key=active_key
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
                    api_key=active_key
                )
                return response.choices[0].message.content.strip()
                
        except Exception as e:
            err_str = str(e)
            is_quota = "quota" in err_str.lower() or "limit" in err_str.lower() or "exhausted" in err_str.lower() or "429" in err_str
            
            if is_quota:
                friendly_error = (
                    "Gemini API Quota/Rate Limit Exhausted. "
                    "Your active API key has run out of quota. "
                    "Please wait for the limit to reset, or configure a new API key under the 'API Provider' panel at the top."
                )
                if "exhausted" in err_str.lower() or "quota" in err_str.lower():
                    # Quota fully depleted - fail immediately without waiting
                    print(f"\n[Gateway API Quota Exhausted] Failing query immediately: {err_str}")
                    raise ValueError(friendly_error)
                
                # Transient rate limit - retry up to max_retries
                if attempt == max_retries - 1:
                    print(f"\n[Gateway API Rate Limit] Maximum retries reached. Failing query: {err_str}")
                    raise ValueError(friendly_error)
                    
                print(f"   [Gateway API Rate Limit] Sleeping {backoff} seconds before retry (Attempt {attempt+1}/{max_retries})...")
                time.sleep(backoff)
                backoff *= 2
            else:
                print(f"LLM Gateway Error calling {model}: {e}")
                raise e
    raise ValueError("LLM Gateway failed to return a response after retries.")

