import os
from typing import List
from dotenv import load_dotenv

# Ensure environment is loaded from project root
workspace_env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".env")
load_dotenv(dotenv_path=workspace_env_path)

class Settings:
    # Database connection parameters
    DB_HOST: str = os.getenv("DB_HOST", "localhost")
    DB_PORT: str = os.getenv("DB_PORT", "5432")
    DB_USER: str = os.getenv("DB_USER", "postgres")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "")
    DB_NAME: str = os.getenv("DB_NAME", "querypilot")
    
    # API key
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    
    # CORS setup: Allow development hosts by default, plus production origins from env
    CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]
    
    # Add custom deployment/production domains if configured
    extra_origins = os.getenv("CORS_ORIGINS")
    if extra_origins:
        for origin in extra_origins.split(","):
            cleaned = origin.strip()
            if cleaned and cleaned not in CORS_ORIGINS:
                CORS_ORIGINS.append(cleaned)

settings = Settings()
