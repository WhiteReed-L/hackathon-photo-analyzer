from pathlib import Path

import config
from database import (
    create_asset,
    create_generation_job,
    get_asset_by_filename,
    get_generation_job,
    get_user_by_id,
    record_ai_run,
    save_conversation,
    save_conversation_message,
    update_generation_job,
)
from models import GenerateRequest, GenerateResponse
from services.image_gen import build_final_prompt, compress_image, generate_image, generate_styled_image
from services.prompt_engine import PromptEngine
from services.style_parser import parse_style_structured, style_brief_to_directive
from services.vision_service import analyze_photos


class GenerationError(Exception):
    pass


class UserNotFoundError(GenerationError):
    pass


async def create_job(user_id: int, body: GenerateRequest) -> int:
    return await create_generation_job(user_id, body.model_dump(), status="queued")


async def run_job(job_id: int) -> GenerateResponse:
    job = await get_generation_job(job_id)
    if not job:
        raise GenerationError("Generation job not found")
    body = GenerateRequest(**job["input_json"])
    await update_generation_job(job_id, status="running")
    try:
        result = await generate_outfit(user_id=job["user_id"], body=body, job_id=job_id)
        await update_generation_job(job_id, status="succeeded")
        return result
    except Exception as exc:
        await update_generation_job(job_id, status="failed", error_message=str(exc))
        raise


async def generate_outfit(user_id: int, body: GenerateRequest, job_id: int | None = None) -> GenerateResponse:
    if job_id is None:
        job_id = await create_generation_job(user_id, body.model_dump(), status="running")
    if body.previous_job_id:
        await update_generation_job(job_id, previous_job_id=body.previous_job_id)

    user = await get_user_by_id(user_id)
    if not user:
        raise UserNotFoundError("用户不存在")

    image_context = _resolve_image_context(body)
    user_photo_path = await _local_path_from_url(image_context["user_photo_url"], user_id)
    outfit_reference_path = await _local_path_from_url(image_context["outfit_reference_url"], user_id)
    base_image_path = await _local_path_from_url(image_context["base_image_url"], user_id)
    previous_result_path = await _local_path_from_url(image_context["previous_result_url"], user_id)
    edit_base_path = base_image_path or previous_result_path or user_photo_path
    generation_mode = _select_generation_mode(
        user_photo_path=user_photo_path,
        outfit_reference_path=outfit_reference_path,
        base_image_path=base_image_path,
        previous_result_path=previous_result_path,
    )
    reference_strength = image_context["reference_strength"]

    vision_result = await analyze_photos(user_photo_path, outfit_reference_path)
    await record_ai_run(
        job_id=job_id,
        step="vision",
        status="succeeded",
        model=config.OPENAI_VISION_MODEL,
        input_data={
            "image_context": image_context,
            "generation_mode": generation_mode,
            "has_user_photo": bool(user_photo_path),
            "has_outfit_reference": bool(outfit_reference_path),
            "has_edit_base": bool(edit_base_path),
        },
        output_text=str(vision_result),
    )

    identity_features = vision_result["identity_features"] or _identity_from_profile(user)
    clothing_analysis = vision_result["clothing_analysis"]
    gender_hint, season_hint, occasion_hint = _guess_hints(
        identity_features, body.style_tags or [], body.scene_tags or []
    )

    raw_text = (body.text or "") + (
        f"\nClothing type preferences: {', '.join(body.clothing_tags)}." if body.clothing_tags else ""
    )
    all_tags = list(body.style_tags or []) + list(body.scene_tags or [])

    style_directive, style_brief = await parse_style_structured(
        raw_text=raw_text or "Create a fashionable outfit suitable for the user.",
        tags=all_tags,
        gender_hint=gender_hint,
        season_hint=season_hint,
        occasion_hint=occasion_hint,
        identity_features=identity_features,
        clothing_analysis=clothing_analysis,
    )
    previous_job = await get_generation_job(body.previous_job_id, user_id) if body.previous_job_id else None
    if previous_job and previous_job.get("style_brief_json") and body.patch:
        style_brief = _merge_style_brief(previous_job["style_brief_json"], body.patch)
        style_directive = style_brief_to_directive(style_brief)

    current_outfit_state = _current_outfit_state_from_brief(style_brief)
    await record_ai_run(
        job_id=job_id,
        step="style_parse",
        status="succeeded",
        model=config.OPENAI_TEXT_MODEL,
        input_data={
            "text": raw_text,
            "tags": all_tags,
            "generation_mode": generation_mode,
            "reference_strength": reference_strength,
            "chat_intent": body.chat_intent,
            "patch": body.patch,
            "constraints": body.constraints,
            "previous_job_id": body.previous_job_id,
        },
        output_text=style_directive,
    )

    final_prompt = build_final_prompt(
        identity_features=identity_features,
        style_directive=style_directive,
        mode=generation_mode,
        reference_strength=reference_strength,
    )
    await update_generation_job(
        job_id,
        vision_result=str(vision_result),
        style_directive=style_directive,
        style_brief_json=style_brief,
        current_outfit_state_json=current_outfit_state,
        final_prompt=final_prompt,
    )

    try:
        if edit_base_path and Path(edit_base_path).exists():
            image_result = await generate_styled_image(prompt=final_prompt, reference_image_path=edit_base_path)
        elif outfit_reference_path and Path(outfit_reference_path).exists():
            # Explicitly use reference image only as an outfit/style visual reference.
            image_result = await generate_styled_image(prompt=final_prompt, reference_image_path=outfit_reference_path)
        else:
            image_result = await generate_image(final_prompt)
    except Exception as exc:
        await record_ai_run(
            job_id=job_id,
            step="image_generate",
            status="failed",
            model=config.OPENAI_MODEL,
            prompt=final_prompt,
            error=str(exc),
        )
        raise

    await record_ai_run(
        job_id=job_id,
        step="image_generate",
        status="succeeded",
        model=config.OPENAI_MODEL,
        prompt=final_prompt,
        input_data={"generation_mode": generation_mode, "reference_strength": reference_strength},
        output_text=image_result.get("revised_prompt"),
    )

    description = _build_description(style_directive)
    original_url, thumb_url, output_asset_id = await _register_generated_assets(user_id, image_result)

    await save_conversation(
        user_id=user_id,
        role="user",
        text=body.text,
        image_url=image_context["user_photo_url"] or image_context["outfit_reference_url"] or image_context["base_image_url"],
        clothing_tags=body.clothing_tags,
        style_tags=body.style_tags,
        scene_tags=body.scene_tags,
    )
    conv_id = await save_conversation(
        user_id=user_id,
        role="assistant",
        image_url=original_url,
        text=description or image_result["revised_prompt"],
    )
    await save_conversation_message(
        user_id=user_id,
        role="assistant",
        text=description or image_result["revised_prompt"],
        asset_id=output_asset_id,
        generation_job_id=job_id,
        metadata={
            "thumbnail_url": thumb_url,
            "original_url": original_url,
            "generation_mode": generation_mode,
            "reference_strength": reference_strength,
            "image_context": image_context,
            "style_brief": style_brief,
            "current_outfit_state": current_outfit_state,
        },
    )

    response = GenerateResponse(
        image_url=thumb_url,
        original_url=original_url,
        revised_prompt=image_result["revised_prompt"],
        description=description,
        conversation_id=conv_id,
        job_id=job_id,
    )
    result_payload = response.model_dump()
    result_payload.update({
        "style_brief": style_brief,
        "current_outfit_state": current_outfit_state,
        "generation_mode": generation_mode,
        "reference_strength": reference_strength,
    })
    await update_generation_job(job_id, status="succeeded", output_asset_id=output_asset_id, result_json=result_payload)
    return response


def _merge_style_brief(previous: dict, patch: dict) -> dict:
    """Deep-merge a chat patch into the previous structured styling brief."""
    merged = dict(previous or {})
    for key, value in (patch or {}).items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            nested = dict(merged[key])
            nested.update({k: v for k, v in value.items() if v is not None})
            merged[key] = nested
        elif value is not None:
            merged[key] = value
    return merged


def _current_outfit_state_from_brief(brief: dict) -> dict:
    return {
        "top_garment": brief.get("top_garment"),
        "bottom_garment": brief.get("bottom_garment"),
        "footwear": brief.get("footwear"),
        "accessories": brief.get("accessories"),
        "color_palette": brief.get("color_palette"),
        "materials": brief.get("materials"),
        "silhouette": brief.get("silhouette"),
        "style_name": brief.get("style_name"),
    }


def _resolve_image_context(body: GenerateRequest) -> dict:
    """Normalize old and new image fields into explicit AI semantics."""
    user_photo_url = body.user_photo_url or body.user_image_url
    previous_result_url = body.previous_result_url
    base_image_url = body.base_image_url or previous_result_url
    outfit_reference_url = body.outfit_reference_url

    # Legacy compatibility: reference_image_url used to mean outfit reference on
    # initial pages, but in chat follow-up it often means the previous/base image.
    if body.reference_image_url:
        if base_image_url:
            outfit_reference_url = outfit_reference_url or body.reference_image_url
        elif body.path == "chat" or previous_result_url:
            base_image_url = body.reference_image_url
        else:
            outfit_reference_url = outfit_reference_url or body.reference_image_url

    reference_strength = body.reference_strength
    if reference_strength not in ("very_strict", "strict", "inspiration"):
        reference_strength = "very_strict" if body.path == "a" else "inspiration"

    return {
        "user_photo_url": user_photo_url,
        "outfit_reference_url": outfit_reference_url,
        "base_image_url": base_image_url,
        "previous_result_url": previous_result_url,
        "path": body.path,
        "reference_strength": reference_strength,
    }


def _select_generation_mode(
    user_photo_path: str | None,
    outfit_reference_path: str | None,
    base_image_path: str | None,
    previous_result_path: str | None,
) -> str:
    if previous_result_path or base_image_path:
        return "previous_result_edit"
    if user_photo_path:
        return "user_photo_edit"
    if outfit_reference_path:
        return "reference_outfit_generation"
    return "text_to_image_generation"


async def _local_path_from_url(url: str | None, user_id: int) -> str | None:
    if not url:
        return None
    prefix = "/api/uploads/"
    if not url.startswith(prefix):
        return None
    filename = url[len(prefix):]
    asset = await get_asset_by_filename(filename)
    if not asset or asset["user_id"] != user_id:
        return None
    path = config.UPLOAD_DIR / filename
    return str(path) if path.exists() else None


def _identity_from_profile(user: dict) -> str:
    parts = []
    for key, label in (("height", "Height"), ("weight", "Weight"), ("bust", "Bust"), ("waist", "Waist"), ("hip", "Hip")):
        if user.get(key):
            unit = "kg" if key == "weight" else "cm"
            parts.append(f"{label}: {user[key]}{unit}")
    return "## USER BODY DATA\n" + "\n".join(parts) if parts else "## USER BODY DATA\nNo detailed body data provided."


def _build_description(style_directive: str) -> str:
    brief = PromptEngine.parse_styling_brief(style_directive)
    if not brief:
        return ""
    style_parts = []
    for key in ("Top Garment", "Bottom Garment", "Footwear", "Accessories"):
        val = brief.get(key, "").strip()
        if val and val.lower() != "none":
            label = {"Top Garment": "上装", "Bottom Garment": "下装", "Footwear": "鞋履", "Accessories": "配饰"}[key]
            style_parts.append(f"{label}：{val}")
    parts = []
    if style_parts:
        parts.append("衣服样式：" + "；".join(style_parts))
    if brief.get("Color Palette"):
        parts.append(f"颜色：{brief['Color Palette']}")
    if brief.get("Materials & Textures"):
        parts.append(f"材质：{brief['Materials & Textures']}")
    return "\n".join(parts)


def _guess_hints(identity_text: str, style_tags: list[str], scene_tags: list[str]) -> tuple[str, str, str]:
    gender_hint = "neutral"
    parsed = PromptEngine.parse_identity_text(identity_text) if identity_text else {}
    gender_raw = parsed.get("GENDER", "").lower()
    if "female" in gender_raw or "女" in gender_raw:
        gender_hint = "female"
    elif "male" in gender_raw or "男" in gender_raw:
        gender_hint = "male"

    all_tags = [t.lower() for t in (style_tags or []) + (scene_tags or [])]
    season_hint = _first_matching_tag(all_tags, {
        "spring": ["春季", "春天", "春装", "spring"],
        "summer": ["夏季", "夏天", "夏装", "summer", "海滩度假", "海边"],
        "autumn": ["秋季", "秋天", "秋装", "autumn", "fall", "复古"],
        "winter": ["冬季", "冬天", "冬装", "winter", "羽绒服", "大衣"],
    }) or "none"
    occasion_hint = _first_matching_tag(all_tags, {
        "daily": ["日常", "通勤", "居家", "日常出行", "daily"],
        "work": ["工作", "面试", "商务会议", "职场", "work", "office"],
        "date": ["约会", "date", "浪漫"],
        "party": ["派对", "聚会", "晚宴", "婚礼", "party", "festival"],
        "outdoor": ["户外", "徒步", "旅行", "运动健身", "outdoor", "travel"],
    }) or "none"
    return gender_hint, season_hint, occasion_hint


def _first_matching_tag(tags: list[str], mapping: dict[str, list[str]]) -> str | None:
    for name, keywords in mapping.items():
        if any(keyword in tag for tag in tags for keyword in keywords):
            return name
    return None


async def _register_generated_assets(user_id: int, image_result: dict) -> tuple[str, str, int | None]:
    local_path = image_result.get("local_path")
    original_url = image_result["image_url"]
    thumb_url = original_url
    output_asset_id = None
    if not local_path or not Path(local_path).exists():
        return original_url, thumb_url, output_asset_id

    output_path = Path(local_path)
    try:
        output_asset_id = await create_asset(
            user_id=user_id,
            type="generated_image",
            filename=output_path.name,
            mime_type="image/png",
            size_bytes=output_path.stat().st_size,
        )
    except Exception:
        output_asset_id = None

    try:
        thumb_name = await compress_image(local_path)
        thumb_path = config.UPLOAD_DIR / thumb_name
        await create_asset(
            user_id=user_id,
            type="thumbnail",
            filename=thumb_name,
            mime_type="image/jpeg",
            size_bytes=thumb_path.stat().st_size if thumb_path.exists() else None,
            source_asset_id=output_asset_id,
        )
        thumb_url = f"/api/uploads/{thumb_name}"
    except Exception:
        thumb_url = original_url
    return original_url, thumb_url, output_asset_id
