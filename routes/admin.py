from fastapi import APIRouter, Depends, HTTPException

import config
from database import get_all_photos, get_photo_by_id, get_photo_count, update_photo_analysis
from models import AnalysisResponse, PhotoListResponse, PhotoResponse
from routes.auth import require_admin
from services.llm import analyze_image

router = APIRouter()


def _make_image_url(filename: str) -> str:
    return f"/api/uploads/{filename}"


@router.get(
    "/photos",
    response_model=PhotoListResponse,
    dependencies=[Depends(require_admin)],
)
async def list_photos(limit: int = 50, offset: int = 0):
    photos = await get_all_photos(limit=limit, offset=offset)
    total = await get_photo_count()
    for p in photos:
        p["image_url"] = _make_image_url(p["filename"])
    return PhotoListResponse(photos=photos, total=total)


@router.get(
    "/photos/{photo_id}",
    response_model=PhotoResponse,
    dependencies=[Depends(require_admin)],
)
async def get_photo(photo_id: int):
    photo = await get_photo_by_id(photo_id)
    if not photo:
        raise HTTPException(status_code=404, detail="Photo not found")
    photo["image_url"] = _make_image_url(photo["filename"])
    return photo


@router.post(
    "/photos/{photo_id}/analyze",
    response_model=AnalysisResponse,
    dependencies=[Depends(require_admin)],
)
async def analyze_photo(photo_id: int):
    photo = await get_photo_by_id(photo_id)
    if not photo:
        raise HTTPException(status_code=404, detail="Photo not found")

    file_path = config.UPLOAD_DIR / photo["filename"]
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Photo file not found on disk")

    if not config.OPENAI_API_KEY or config.OPENAI_API_KEY == "sk-your-key-here":
        raise HTTPException(
            status_code=502,
            detail="OpenAI API key not configured. Set OPENAI_API_KEY in .env file.",
        )

    try:
        result = await analyze_image(str(file_path))
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"AI analysis failed: {str(e)}",
        )

    await update_photo_analysis(photo_id, result["analysis"])

    return AnalysisResponse(
        id=photo_id,
        analysis=result["analysis"],
        model=result["model"],
        usage=result["usage"],
    )
