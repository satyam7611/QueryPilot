import uuid
from typing import Optional
from fastapi import APIRouter, File, UploadFile, HTTPException, Response, Cookie
from app.services.dataset_service import (
    process_and_save_dataset,
    get_dataset_ddl,
    delete_user_dataset
)

router = APIRouter()

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB limit

def get_or_create_session(response: Response, querypilot_session: Optional[str] = Cookie(None)) -> str:
    """Helper that retrieves or sets a unique anonymous session ID to isolate datasets."""
    if querypilot_session:
        return querypilot_session
    # Create secure anonymous session ID
    session_id = str(uuid.uuid4())
    response.set_cookie(
        key="querypilot_session",
        value=session_id,
        httponly=True,
        samesite="lax",
        secure=False  # Set to True in production HTTPS
    )
    return session_id

@router.post("/datasets/upload")
async def upload_dataset(
    response: Response,
    file: UploadFile = File(...),
    querypilot_session: Optional[str] = Cookie(None)
):
    """
    Handles CSV and Excel uploads.
    Validates file sizes and formats, and populates isolated database tables.
    """
    session_id = get_or_create_session(response, querypilot_session)
    
    # 1. Validate File Types
    filename = file.filename
    if not (filename.endswith(".csv") or filename.endswith(".xlsx")):
        raise HTTPException(status_code=400, detail="Only CSV and XLSX file types are supported.")
        
    # 2. Validate File Size
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File size exceeds the 10MB limit.")
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
        
    # 3. Process File Content and Seed Database
    try:
        dataset_id = process_and_save_dataset(
            file_bytes=content,
            filename=filename,
            session_id=session_id
        )
        return {
            "status": "success",
            "message": "Dataset uploaded and processed successfully.",
            "dataset_id": dataset_id,
            "filename": filename
        }
    except ValueError as val_err:
        raise HTTPException(status_code=400, detail=str(val_err))
    except Exception as e:
        print(f"[Datasets API Error] Processing failed: {e}")
        raise HTTPException(status_code=500, detail="Internal processing error. The file structure may be malformed.")

@router.get("/datasets/{dataset_id}/schema")
def get_schema(
    dataset_id: str,
    response: Response,
    querypilot_session: Optional[str] = Cookie(None)
):
    """Retrieves the dynamic DDL schema details for an uploaded dataset."""
    # Ensure session is active
    _ = get_or_create_session(response, querypilot_session)
    try:
        ddl = get_dataset_ddl(dataset_id)
        return {
            "dataset_id": dataset_id,
            "ddl": ddl
        }
    except ValueError as val_err:
        raise HTTPException(status_code=404, detail=str(val_err))
    except Exception as e:
        print(f"[Datasets API Error] Schema retrieval failed: {e}")
        raise HTTPException(status_code=500, detail="Internal error loading dataset schema.")

@router.delete("/datasets/{dataset_id}")
def delete_dataset(
    dataset_id: str,
    response: Response,
    querypilot_session: Optional[str] = Cookie(None)
):
    """Deletes a custom user dataset and drops its PostgreSQL table."""
    session_id = get_or_create_session(response, querypilot_session)
    try:
        success = delete_user_dataset(dataset_id, session_id)
        if not success:
            raise HTTPException(status_code=404, detail="Dataset not found or access denied.")
        return {
            "status": "success",
            "message": f"Dataset {dataset_id} successfully deleted."
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"[Datasets API Error] Deletion failed: {e}")
        raise HTTPException(status_code=500, detail="Internal error deleting dataset.")
