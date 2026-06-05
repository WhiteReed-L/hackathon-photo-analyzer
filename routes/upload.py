import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

import config
from database import insert_photo
from models import UploadResponse

router = APIRouter()


@router.post("/upload", response_model=UploadResponse)
async def upload_photo(file: UploadFile = File(...)):
    # 1. Validate extension
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    ext = Path(file.filename).suffix.lower()
    if ext not in config.ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {ext}. Allowed: {', '.join(config.ALLOWED_EXTENSIONS)}",
        )

    # 2. Read and validate size
    contents = await file.read()
    max_bytes = config.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if len(contents) > max_bytes:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size: {config.MAX_UPLOAD_SIZE_MB}MB",
        )

    # 3. Generate unique filename and save
    unique_name = f"{uuid.uuid4()}{ext}"
    file_path = config.UPLOAD_DIR / unique_name
    with open(file_path, "wb") as f:
        f.write(contents)

    # 4. Store metadata in database — roll back file on DB failure
    try:
        photo_id = await insert_photo(
            filename=unique_name,
            original_name=file.filename,
            mime_type=file.content_type or "image/jpeg",
            file_size=len(contents),
        )
    except Exception:
        # Clean up orphan file so DB and disk stay consistent
        if file_path.exists():
            file_path.unlink()
        raise HTTPException(
            status_code=500,
            detail="Failed to save photo metadata. Please try again.",
        )

    return UploadResponse(id=photo_id, filename=unique_name, status="uploaded")
