"""POST /api/upload — save reference image to disk. No DB insert needed."""
import io
import secrets
import time
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from PIL import Image, UnidentifiedImageError
import qrcode

try:
    from pillow_heif import register_heif_opener

    register_heif_opener()
except Exception:
    # HEIC support is optional; normal JPG/PNG uploads still work.
    pass

import config
from database import create_asset, get_asset_by_filename
from limiter import limiter
from models import UploadResponse
from routes.user import require_user
from services.storage import storage

router = APIRouter()

SCAN_UPLOAD_TTL_SECONDS = 10 * 60
_scan_uploads: dict[str, dict] = {}


def _cleanup_scan_uploads() -> None:
    now = time.time()
    expired = [token for token, data in _scan_uploads.items() if now - data["created_at"] > SCAN_UPLOAD_TTL_SECONDS]
    for token in expired:
        _scan_uploads.pop(token, None)


def _safe_public_base_url(request: Request) -> str:
    host = request.headers.get("host") or request.url.netloc
    return f"{request.url.scheme}://{host}".rstrip("/")


def _process_image(contents: bytes) -> tuple[bytes, int, int]:
    try:
        Image.MAX_IMAGE_PIXELS = config.MAX_IMAGE_PIXELS
        with Image.open(io.BytesIO(contents)) as img:
            img.verify()
        with Image.open(io.BytesIO(contents)) as img:
            img = img.convert("RGB")
            width, height = img.size
            output = io.BytesIO()
            img.save(output, format="JPEG", quality=92, optimize=True)
            return output.getvalue(), width, height
    except (UnidentifiedImageError, OSError, ValueError):
        raise HTTPException(status_code=400, detail="Invalid image file")


async def _save_uploaded_image(
    user_id: int,
    file: UploadFile,
    asset_type: str = "upload",
    enforce_extension: bool = True,
) -> UploadResponse:
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    ext = Path(file.filename).suffix.lower()
    allowed = config.ALLOWED_EXTENSIONS | {".heic", ".heif"}
    if enforce_extension and ext not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {ext}. Allowed: {', '.join(sorted(allowed))}",
        )

    contents = await file.read()
    max_bytes = config.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if len(contents) > max_bytes:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size: {config.MAX_UPLOAD_SIZE_MB}MB",
        )

    safe_contents, width, height = _process_image(contents)
    unique_name, _ = await storage.save_bytes(safe_contents, suffix=".jpg")

    asset_id = await create_asset(
        user_id=user_id,
        type=asset_type,
        filename=unique_name,
        original_filename=file.filename,
        mime_type="image/jpeg",
        size_bytes=len(safe_contents),
        width=width,
        height=height,
    )
    return UploadResponse(id=asset_id, filename=unique_name, status="uploaded")


@router.post("/upload", response_model=UploadResponse)
@limiter.limit(config.UPLOAD_RATE_LIMIT)
async def upload_photo(
    request: Request,
    file: UploadFile = File(...),
    user_id: int = Depends(require_user),
):
    return await _save_uploaded_image(user_id, file)


@router.get("/uploads/{filename}")
async def get_uploaded_file(filename: str, user_id: int = Depends(require_user)):
    asset = await get_asset_by_filename(filename)
    if not asset or asset["user_id"] != user_id:
        raise HTTPException(status_code=404, detail="File not found")
    path = config.UPLOAD_DIR / filename
    if not path.exists() or path.name != filename:
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path, media_type=asset.get("mime_type") or "application/octet-stream")


@router.post("/scan-upload/session")
async def create_scan_upload_session(request: Request, user_id: int = Depends(require_user)):
    """Create a one-time phone upload URL and QR code for the logged-in desktop user."""
    _cleanup_scan_uploads()
    token = secrets.token_urlsafe(24)
    base = _safe_public_base_url(request)
    upload_url = f"{base}/scan-upload.html?token={token}"
    _scan_uploads[token] = {
        "user_id": user_id,
        "created_at": time.time(),
        "status": "pending",
        "filename": None,
        "asset_id": None,
        "upload_url": upload_url,
    }
    return {
        "token": token,
        "upload_url": upload_url,
        "qr_url": f"/api/scan-upload/{token}/qr",
        "expires_in": SCAN_UPLOAD_TTL_SECONDS,
    }


@router.get("/scan-upload/{token}/qr")
async def scan_upload_qr(token: str):
    data = _scan_uploads.get(token)
    if not data:
        raise HTTPException(status_code=404, detail="Upload session not found")
    img = qrcode.make(data["upload_url"])
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return StreamingResponse(buf, media_type="image/png")


@router.get("/scan-upload/{token}/status")
async def scan_upload_status(token: str, user_id: int = Depends(require_user)):
    data = _scan_uploads.get(token)
    if not data or data["user_id"] != user_id:
        raise HTTPException(status_code=404, detail="Upload session not found")
    return {
        "status": data["status"],
        "filename": data.get("filename"),
        "asset_id": data.get("asset_id"),
        "image_url": f"/api/uploads/{data['filename']}" if data.get("filename") else None,
    }


@router.post("/scan-upload/{token}", response_model=UploadResponse)
async def phone_scan_upload(token: str, file: UploadFile = File(...)):
    _cleanup_scan_uploads()
    data = _scan_uploads.get(token)
    if not data:
        raise HTTPException(status_code=404, detail="Upload session expired or not found")
    if data["status"] == "done":
        raise HTTPException(status_code=409, detail="This upload session has already been used")
    result = await _save_uploaded_image(data["user_id"], file, asset_type="scan_upload", enforce_extension=False)
    data.update({
        "status": "done",
        "filename": result.filename,
        "asset_id": result.id,
    })
    return result
