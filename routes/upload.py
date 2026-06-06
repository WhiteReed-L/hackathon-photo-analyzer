"""POST /api/upload — save reference image to disk. No DB insert needed."""
import uuid
from pathlib import Path

import aiofiles
from fastapi import APIRouter, File, HTTPException, Request, UploadFile

import config
from limiter import limiter
from models import UploadResponse

router = APIRouter()


@router.post("/upload", response_model=UploadResponse)
@limiter.limit("30/minute")
async def upload_photo(request: Request, file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    ext = Path(file.filename).suffix.lower()
    if ext not in config.ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {ext}. Allowed: {', '.join(config.ALLOWED_EXTENSIONS)}",
        )

    contents = await file.read()
    max_bytes = config.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if len(contents) > max_bytes:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size: {config.MAX_UPLOAD_SIZE_MB}MB",
        )

    unique_name = f"{uuid.uuid4()}{ext}"
    file_path = config.UPLOAD_DIR / unique_name
    async with aiofiles.open(file_path, "wb") as f:
        await f.write(contents)

    return UploadResponse(id=0, filename=unique_name, status="uploaded")
