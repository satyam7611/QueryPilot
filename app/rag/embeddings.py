import os
from typing import Optional
from google import genai
from dotenv import load_dotenv

# Load env variables explicitly
workspace_env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env")
load_dotenv(dotenv_path=workspace_env_path, override=True)

def get_embedding(text: str, api_key: Optional[str] = None) -> list[float]:
    """
    Generates a text embedding vector using Google's text-embedding-001 model.
    Returns a list of floats representing the vector.
    """
    # If user provided a Groq key (e.g. starting with 'gsk_'), fall back to environment GEMINI_API_KEY for embeddings
    if api_key and (api_key.startswith("gsk_") or not os.getenv("GEMINI_API_KEY")):
        active_key = api_key if not api_key.startswith("gsk_") else os.getenv("GEMINI_API_KEY")
    else:
        active_key = api_key or os.getenv("GEMINI_API_KEY")

    if not active_key:
        raise ValueError("GEMINI_API_KEY is not configured in the environment.")
        
    try:
        client = genai.Client(api_key=active_key)
        response = client.models.embed_content(
            model='gemini-embedding-001',
            contents=text
        )
        # Extract the vector values
        return response.embeddings[0].values
    except Exception as e:
        print(f"Error generating embedding: {e}")
        raise e
