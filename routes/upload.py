"""POST /api/upload — save reference image to disk. No DB insert needed."""
import io
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from PIL import Image, UnidentifiedImageError

import config
from database import create_asset, get_asset_by_filename
from limiter import limiter
from models import UploadResponse
from routes.user import require_user
from services.storage import storage

router = APIRouter()


@router.post("/upload", response_model=UploadResponse)
@limiter.limit(config.UPLOAD_RATE_LIMIT)
async def upload_photo(
    request: Request,
    file: UploadFile = File(...),
    user_id: int = Depends(require_user),
):
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

    try:
        Image.MAX_IMAGE_PIXELS = config.MAX_IMAGE_PIXELS
        with Image.open(io.BytesIO(contents)) as img:
            img.verify()
        with Image.open(io.BytesIO(contents)) as img:
            img = img.convert("RGB")
            width, height = img.size
            output = io.BytesIO()
            img.save(output, format="JPEG", quality=92, optimize=True)
            safe_contents = output.getvalue()
    except (UnidentifiedImageError, OSError, ValueError):
        raise HTTPException(status_code=400, detail="Invalid image file")

    unique_name, file_path = await storage.save_bytes(safe_contents, suffix=".jpg")

    asset_id = await create_asset(
        user_id=user_id,
        type="upload",
        filename=unique_name,
        original_filename=file.filename,
        mime_type="image/jpeg",
        size_bytes=len(safe_contents),
        width=width,
        height=height,
    )

    return UploadResponse(id=asset_id, filename=unique_name, status="uploaded")


@router.get("/uploads/{filename}")
async def get_uploaded_file(filename: str, user_id: int = Depends(require_user)):
    asset = await get_asset_by_filename(filename)
    if not asset or asset["user_id"] != user_id:
        raise HTTPException(status_code=404, detail="File not found")
    path = config.UPLOAD_DIR / filename
    if not path.exists() or path.name != filename:
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path, media_type=asset.get("mime_type") or "application/octet-stream")
