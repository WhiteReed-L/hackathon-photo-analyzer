"""POST /api/generate — assemble prompt, call DALL-E, save conversation."""
import uuid
from pathlib import Path

import aiofiles
import httpx
from fastapi import APIRouter, Depends, HTTPException

import config
from database import get_user_by_id, save_conversation
from models import GenerateRequest, GenerateResponse
from routes.user import require_user
from services.image_gen import build_prompt, compress_image, generate_image

router = APIRouter()


async def _download_and_save(image_url: str) -> tuple[str, str]:
    """Download DALL-E image, save original + compressed thumbnail.
    Returns (original_filename, thumb_filename).
    """
    async with httpx.AsyncClient() as client:
        resp = await client.get(image_url)
        resp.raise_for_status()

    # Save original
    orig_name = f"{uuid.uuid4()}.png"
    orig_path = config.UPLOAD_DIR / orig_name
    async with aiofiles.open(orig_path, "wb") as f:
        await f.write(resp.content)

    # Create compressed preview
    thumb_name = await compress_image(str(orig_path))
    return orig_name, thumb_name


@router.post("/generate", response_model=GenerateResponse)
async def generate(
    body: GenerateRequest,
    user_id: int = Depends(require_user),
):
    user = await get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    # Build the prompt
    prompt = build_prompt(
        height=user["height"],
        weight=user["weight"],
        bust=user.get("bust"),
        waist=user.get("waist"),
        hip=user.get("hip"),
        text=body.text,
        clothing_tags=body.clothing_tags,
        style_tags=body.style_tags,
        scene_tags=body.scene_tags,
        has_user_photo=body.user_image_url is not None,
        has_reference=body.reference_image_url is not None,
    )

    # Call DALL-E
    try:
        result = await generate_image(prompt)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"图片生成失败: {str(e)}")

    # Download / process image
    if result["image_url"].startswith("/api/uploads/"):
        # Already local (e.g. from b64_json relay) — just compress
        try:
            local_path = str(config.UPLOAD_DIR / result["image_url"].split("/")[-1])
            thumb_name = await compress_image(local_path)
            original_url = result["image_url"]
            thumb_url = f"/api/uploads/{thumb_name}"
        except Exception:
            original_url = result["image_url"]
            thumb_url = result["image_url"]
    else:
        try:
            orig_name, thumb_name = await _download_and_save(result["image_url"])
            original_url = f"/api/uploads/{orig_name}"
            thumb_url = f"/api/uploads/{thumb_name}"
        except Exception:
            original_url = result["image_url"]
            thumb_url = result["image_url"]

    # Save both sides of the conversation AFTER success
    conv_user_id = await save_conversation(
        user_id=user_id,
        role="user",
        text=body.text,
        image_url=body.reference_image_url,
        style_tags=body.style_tags,
        scene_tags=body.scene_tags,
    )
    conv_id = await save_conversation(
        user_id=user_id,
        role="assistant",
        image_url=original_url,
        text=result["revised_prompt"],
    )

    return GenerateResponse(
        image_url=thumb_url,
        original_url=original_url,
        revised_prompt=result["revised_prompt"],
        conversation_id=conv_id,
    )
