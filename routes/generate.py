"""POST /api/generate — Vision + Standard Portrait + Style Parser + PromptEngine + GPT Image 2."""
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

import config
from database import get_user_by_id, save_conversation
from models import GenerateRequest, GenerateResponse
from routes.user import require_user
from services.image_gen import (
    build_final_prompt,
    compress_image,
    generate_image,
    generate_standard_portrait,
    generate_styled_image,
)
from services.prompt_engine import PromptEngine
from services.style_parser import parse_style
from services.vision_service import analyze_photos

router = APIRouter()


def _local_path_from_url(url: str | None) -> str | None:
    """Convert /api/uploads/filename to local filesystem path."""
    if not url:
        return None
    prefix = "/api/uploads/"
    if url.startswith(prefix):
        filename = url[len(prefix):]
        path = config.UPLOAD_DIR / filename
        if path.exists():
            return str(path)
    return None


def _guess_hints(identity_text: str, style_tags: list[str], scene_tags: list[str]) -> tuple[str, str, str]:
    """Infer gender/season/occasion hints from vision output and tags."""
    gender_hint = "neutral"
    if identity_text:
        parsed = PromptEngine.parse_identity_text(identity_text)
        gender_raw = parsed.get("GENDER", "").lower()
        if "female" in gender_raw or "女" in gender_raw:
            gender_hint = "female"
        elif "male" in gender_raw or "男" in gender_raw:
            gender_hint = "male"

    season_hint = "none"
    occasion_hint = "none"
    all_tags = [t.lower() for t in (style_tags or []) + (scene_tags or [])]
    season_keywords = {
        "spring": ["春季", "春天", "春装", "spring"],
        "summer": ["夏季", "夏天", "夏装", "summer", "海滩度假", "海边"],
        "autumn": ["秋季", "秋天", "秋装", "autumn", "fall", "复古"],
        "winter": ["冬季", "冬天", "冬装", "winter", "羽绒服", "大衣"],
    }
    occasion_keywords = {
        "daily": ["日常", "通勤", "居家", "日常出行", "daily"],
        "work": ["工作", "面试", "商务会议", "职场", "work", "office"],
        "date": ["约会", "date", "浪漫"],
        "party": ["派对", "聚会", "晚宴", "婚礼", "party", "festival"],
        "outdoor": ["户外", "徒步", "旅行", "运动健身", "outdoor", "travel"],
    }

    for season, kws in season_keywords.items():
        if any(kw in tag for tag in all_tags for kw in kws):
            season_hint = season
            break

    for occasion, kws in occasion_keywords.items():
        if any(kw in tag for tag in all_tags for kw in kws):
            occasion_hint = occasion
            break

    return gender_hint, season_hint, occasion_hint


@router.post("/generate", response_model=GenerateResponse)
async def generate(
    body: GenerateRequest,
    user_id: int = Depends(require_user),
):
    user = await get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    # Resolve uploaded photos to local paths
    user_photo_path = _local_path_from_url(body.user_image_url)
    reference_photo_path = _local_path_from_url(body.reference_image_url)

    # ── Step 0: Vision analysis ─────────────────────────────────────────
    vision_result = await analyze_photos(user_photo_path, reference_photo_path)
    identity_features = vision_result["identity_features"] or ""
    clothing_analysis = vision_result["clothing_analysis"]
    has_user_photo = vision_result["has_user_photo"]

    # If no photo uploaded, build a basic identity description from profile data
    if not identity_features:
        parts = []
        if user.get("height"):
            parts.append(f"Height: {user['height']}cm")
        if user.get("weight"):
            parts.append(f"Weight: {user['weight']}kg")
        if user.get("bust"):
            parts.append(f"Bust: {user['bust']}cm")
        if user.get("waist"):
            parts.append(f"Waist: {user['waist']}cm")
        if user.get("hip"):
            parts.append(f"Hip: {user['hip']}cm")
        identity_features = "## USER BODY DATA\n" + "\n".join(parts) if parts else "## USER BODY DATA\nNo detailed body data provided."

    # ── Step 1: Standard Portrait (only when user photo exists) ─────────
    standard_portrait_url: str | None = None
    standard_portrait_path: str | None = None

    if has_user_photo:
        try:
            std_result = await generate_standard_portrait(identity_features)
            standard_portrait_url = std_result["image_url"]
            standard_portrait_path = std_result.get("local_path")
        except Exception as e:
            # Non-fatal: if Step 1 fails we can still fall back to text-only generation
            print(f"[WARN] Step 1 standard portrait failed: {e}")

    # ── Step 3: Style parsing ───────────────────────────────────────────
    gender_hint, season_hint, occasion_hint = _guess_hints(
        identity_features, body.style_tags or [], body.scene_tags or []
    )

    raw_text = (body.text or "") + (
        f"\nClothing type preferences: {', '.join(body.clothing_tags)}." if body.clothing_tags else ""
    )
    all_tags = list(body.style_tags or []) + list(body.scene_tags or [])

    style_directive = await parse_style(
        raw_text=raw_text or "Create a fashionable outfit suitable for the user.",
        tags=all_tags,
        gender_hint=gender_hint,
        season_hint=season_hint,
        occasion_hint=occasion_hint,
        identity_features=identity_features,
        clothing_analysis=clothing_analysis,
    )

    # ── Step 2: Build final prompt and generate image ───────────────────
    final_prompt = build_final_prompt(
        identity_features=identity_features,
        style_directive=style_directive,
    )

    try:
        if standard_portrait_path and Path(standard_portrait_path).exists():
            result = await generate_styled_image(
                prompt=final_prompt,
                reference_image_path=standard_portrait_path,
            )
        else:
            # Fallback: no user photo or Step 1 failed
            result = await generate_image(final_prompt)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"图片生成失败: {str(e)}")

    # Compress thumbnail for display
    local_path = result.get("local_path")
    if local_path and Path(local_path).exists():
        try:
            thumb_name = await compress_image(local_path)
            original_url = result["image_url"]
            thumb_url = f"/api/uploads/{thumb_name}"
        except Exception:
            original_url = result["image_url"]
            thumb_url = result["image_url"]
    else:
        original_url = result["image_url"]
        thumb_url = result["image_url"]

    # Save both sides of the conversation AFTER success
    conv_user_id = await save_conversation(
        user_id=user_id,
        role="user",
        text=body.text,
        image_url=body.user_image_url or body.reference_image_url,
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
