from fastapi import APIRouter

router = APIRouter()

@router.get("/health")
def check_health():
    """Simple check confirming server viability without hitting DB or LLM."""
    return {"status": "healthy"}
