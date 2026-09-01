from typing import Optional, List
from fastapi import APIRouter, HTTPException, Cookie, Response
from pydantic import BaseModel, Field
from app.services.query_service import execute_query, resume_clarification

router = APIRouter()

class QueryRequest(BaseModel):
    question: str = Field(..., description="The natural language question to ask.")
    dataset_id: Optional[str] = Field(None, description="The custom dataset ID. If null, queries the demo database.")
    api_key: Optional[str] = Field(None, description="User-provided API key (BYOK). Redacted request-scoped parameter.")

class ResumeRequest(BaseModel):
    thread_id: str = Field(..., description="The thread ID of the paused clarification state.")
    choice: str = Field(..., description="The user's option index or text selection.")
    api_key: Optional[str] = Field(None, description="User-provided API key (BYOK) for resuming execution.")

@router.post("/query")
def run_query(request: QueryRequest):
    """
    Submits a natural language query to the Text-to-SQL workflow.
    Resolves automatically or prompts for clarification.
    """
    # Safety redact helper: clean input key trace
    api_key_clean = request.api_key.strip() if request.api_key else None
    
    try:
        result = execute_query(
            question=request.question,
            dataset_id=request.dataset_id,
            api_key=api_key_clean
        )
        return result
    except Exception as e:
        print(f"[Query API Error] Run query failed: {e}")
        # Return generic message to prevent secret/path leakage
        raise HTTPException(
            status_code=500, 
            detail="An error occurred while compiling or validating the SQL query."
        )

@router.post("/query/resume")
def resume_query(request: ResumeRequest):
    """Resumes a paused clarification workflow with the user's choice."""
    api_key_clean = request.api_key.strip() if request.api_key else None
    
    try:
        result = resume_clarification(
            thread_id=request.thread_id,
            choice=request.choice,
            api_key=api_key_clean
        )
        return result
    except Exception as e:
        print(f"[Query API Error] Resume query failed: {e}")
        raise HTTPException(
            status_code=500, 
            detail="Failed to resume clarification thread."
        )
