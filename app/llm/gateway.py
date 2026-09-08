import os
from typing import Type, TypeVar, Optional, List, Dict, Any
import litellm
from pydantic import BaseModel
from dotenv import load_dotenv

# Ensure environment is loaded from the correct workspace path
workspace_env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env")
load_dotenv(dotenv_path=workspace_env_path, override=True)

# Default model configuration
DEFAULT_MODEL = os.getenv("PRIMARY_MODEL", "gemini/gemini-3.8-flash")

T = TypeVar("T", bound=BaseModel)


def resolve_api_key_for_model(model_name: str, user_api_key: Optional[str] = None) -> Optional[str]:
    """
    Resolves the appropriate API key based on the model provider and provided keys.
    """
    clean_key = user_api_key.strip() if user_api_key else None

    if model_name.startswith("groq/"):
        if clean_key and clean_key.startswith("gsk_"):
            return clean_key
        return os.getenv("GROQ_API_KEY")
    elif model_name.startswith("gemini/"):
        if clean_key and not clean_key.startswith("gsk_"):
            return clean_key
        return os.getenv("GEMINI_API_KEY")
    else:
        return clean_key or os.getenv("GEMINI_API_KEY") or os.getenv("GROQ_API_KEY")


def get_candidate_models(requested_model: str) -> List[str]:
    """
    Builds an ordered list of candidate models starting with the requested model,
    followed by configured or intelligent default fallback models.
    """
    candidates = [requested_model]

    custom_fallbacks = os.getenv("FALLBACK_MODELS")
    if custom_fallbacks:
        for m in custom_fallbacks.split(","):
            m = m.strip()
            if m and m not in candidates:
                candidates.append(m)
        return candidates

    # Default fallback cascade
    groq_key = os.getenv("GROQ_API_KEY")
    if groq_key:
        candidates.extend([
            "groq/openai/gpt-oss-120b",
            "groq/openai/gpt-oss-20b",
        ])

    gemini_alternatives = [
        "gemini/gemini-3.7-flash",
        "gemini/gemini-3.6-flash",
        "gemini/gemini-3.5-flash",
    ]
    for m in gemini_alternatives:
        if m not in candidates:
            candidates.append(m)

    if not groq_key:
        candidates.extend([
            "groq/openai/gpt-oss-120b",
            "groq/openai/gpt-oss-20b",
        ])

    return candidates


def is_fallback_worthy_error(err: Exception) -> bool:
    """
    Determines whether an error is transient, capacity-related (503 High Demand),
    or quota-related (429), justifying failover to an alternative model/provider.
    """
    err_str = str(err).lower()
    error_name = err.__class__.__name__.lower()

    if any(token in err_str for token in [
        "503",
        "high demand",
        "spikes in demand",
        "serviceunavailable",
        "unavailable",
        "overloaded",
        "server error",
        "bad gateway",
        "502",
        "504",
        "gateway timeout",
        "timeout",
        "connection reset",
        "connection error",
    ]):
        return True

    if any(token in err_str for token in [
        "429",
        "rate limit",
        "ratelimit",
        "quota",
        "resource exhausted",
        "too many requests",
    ]):
        return True

    if any(token in error_name for token in ["serviceunavailable", "ratelimit", "timeouterror"]):
        return True

    return False


def _parse_structured_output(content: Any, model_cls: Type[T]) -> T:
    """
    Safely validates structured output from raw strings or dictionaries,
    handling markdown code fences if present.
    """
    if content is None:
        raise ValueError("LLM returned empty content for structured output.")
    if isinstance(content, model_cls):
        return content
    if isinstance(content, dict):
        return model_cls.model_validate(content)
    if isinstance(content, str):
        text = content.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines).strip()
        return model_cls.model_validate_json(text)
    raise ValueError(f"Unexpected content type from LLM structured output: {type(content)}")


def query_llm(
    messages: List[Dict[str, str]],
    model: str = DEFAULT_MODEL,
    temperature: float = 0.0,
    response_format: Optional[Type[T]] = None,
    api_key: Optional[str] = None,
) -> str | T:
    """
    Central gateway function to call LLMs via LiteLLM with resilient multi-model fallback.
    Supports regular string responses and structured outputs via Pydantic schemas.
    """
    import time

    candidate_models = get_candidate_models(model)
    attempted_models: List[str] = []
    last_error: Optional[Exception] = None

    for candidate in candidate_models:
        model_key = resolve_api_key_for_model(candidate, user_api_key=api_key)
        if not model_key:
            # Skip candidates that do not have an API key configured
            continue

        attempted_models.append(candidate)
        max_retries = 2
        backoff = 1.0

        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    print(f"   [LLM Gateway] Retrying model '{candidate}' (Attempt {attempt+1}/{max_retries})...")

                if response_format:
                    response = litellm.completion(
                        model=candidate,
                        messages=messages,
                        temperature=temperature,
                        response_format=response_format,
                        api_key=model_key,
                    )
                    raw_content = response.choices[0].message.content
                    result = _parse_structured_output(raw_content, response_format)
                    if candidate != model:
                        print(f"[LLM Gateway Fallback] Successfully answered using fallback model '{candidate}'.")
                    return result
                else:
                    response = litellm.completion(
                        model=candidate,
                        messages=messages,
                        temperature=temperature,
                        api_key=model_key,
                    )
                    content = response.choices[0].message.content.strip()
                    if candidate != model:
                        print(f"[LLM Gateway Fallback] Successfully answered using fallback model '{candidate}'.")
                    return content

            except Exception as e:
                last_error = e
                err_str = str(e).lower()

                # If 503 high demand or capacity failure: fall back to the next model immediately
                if "503" in err_str or "high demand" in err_str or "unavailable" in err_str:
                    print(f"[LLM Gateway Fallback] Model '{candidate}' is experiencing high demand (503). Failing over to next fallback candidate...")
                    break

                # If rate limited (429) or quota exhausted
                if "quota" in err_str or "exhausted" in err_str:
                    print(f"[LLM Gateway Fallback] Model '{candidate}' quota exhausted. Failing over to next fallback candidate...")
                    break

                # For transient errors, retry once before failing over
                if attempt < max_retries - 1 and is_fallback_worthy_error(e):
                    time.sleep(backoff)
                    backoff *= 2
                    continue
                else:
                    print(f"[LLM Gateway Fallback] Model '{candidate}' failed ({e}). Checking next candidate...")
                    break

    # If all models in the cascade failed
    if not attempted_models:
        raise ValueError(
            "No API key is configured. Please provide GEMINI_API_KEY or GROQ_API_KEY in .env or via BYOK."
        )

    raise RuntimeError(
        f"All LLM models in fallback cascade failed ({', '.join(attempted_models)}). "
        f"Last error: {last_error}"
    )

