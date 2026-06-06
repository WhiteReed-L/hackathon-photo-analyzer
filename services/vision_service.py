"""GPT-4o Vision 分析用户照片与服装参考图，输出结构化文本特征。"""
import base64
import io
from pathlib import Path

from PIL import Image

import config
from services.ai_client import default_client
from services.prompt_engine import PromptEngine


_MAX_VISION_PX = 2048


def _resize_for_vision(image_path: str) -> str:
    """Resize image if too large, return base64 JPEG data URI."""
    img = Image.open(image_path)
    img = img.convert("RGB")

    if max(img.width, img.height) > _MAX_VISION_PX:
        ratio = _MAX_VISION_PX / max(img.width, img.height)
        new_size = (int(img.width * ratio), int(img.height * ratio))
        img = img.resize(new_size, Image.LANCZOS)

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
    return f"data:image/jpeg;base64,{b64}"


_VISION_SYSTEM = """You are a forensic fashion analysis system. Your job has two parts:
1. Extract a comprehensive, objective identity profile from the user's own photo.
2. If a reference outfit photo is provided, analyze the clothing style, color palette, materials, silhouette, and key garments.

Follow the output format EXACTLY. Do not add conversational text outside the marked blocks."""


def _build_vision_prompt(engine: PromptEngine, has_reference: bool) -> str:
    base = engine.IDENTITY_EXTRACTION_PROMPT
    clothing_section = """
## CLOTHING ANALYSIS FORMAT (only if reference outfit image is provided)

---CLOTHING ANALYSIS BEGIN---
OverallStyle: [2-4 words summary, e.g. "minimalist workwear"]
ColorPalette: [3-5 dominant colors with shade descriptors]
KeyGarments: [specific upper, lower, outerwear, footwear]
MaterialsTextures: [key fabrics and tactile qualities]
Silhouette: [overall shape, e.g. "structured top / relaxed bottom"]
StylingNotes: [2-3 sentences on how pieces relate]
---CLOTHING ANALYSIS END---
"""
    if has_reference:
        return base + "\n" + clothing_section
    return base + "\nIf no reference outfit image is provided, output ONLY the Identity Profile block."


async def analyze_photos(
    user_photo_path: str | None,
    reference_photo_path: str | None = None,
) -> dict:
    """Analyze user photo and optional reference outfit.

    Returns:
        {
            "identity_features": str,   # raw text between ---IDENTITY PROFILE--- markers
            "clothing_analysis": str | None,
            "has_user_photo": bool,
            "has_reference": bool,
        }
    """
    client = default_client()
    engine = PromptEngine()

    has_user_photo = bool(user_photo_path and Path(user_photo_path).exists())
    has_reference = bool(reference_photo_path and Path(reference_photo_path).exists())

    if not has_user_photo and not has_reference:
        return {
            "identity_features": "",
            "clothing_analysis": None,
            "has_user_photo": False,
            "has_reference": False,
        }

    content: list[dict] = []
    content.append({
        "type": "text",
        "text": _build_vision_prompt(engine, has_reference),
    })

    if has_user_photo:
        content.append({
            "type": "text",
            "text": "Image 1: The user's own photo. Extract identity profile from this person.",
        })
        content.append({
            "type": "image_url",
            "image_url": {"url": _resize_for_vision(str(user_photo_path)), "detail": "high"},
        })

    if has_reference:
        content.append({
            "type": "text",
            "text": "Image 2: Reference outfit photo. Analyze the clothing style, colors, materials and silhouette from this image.",
        })
        content.append({
            "type": "image_url",
            "image_url": {"url": _resize_for_vision(str(reference_photo_path)), "detail": "high"},
        })

    response = await client.chat.completions.create(
        model=config.OPENAI_VISION_MODEL,
        messages=[
            {"role": "system", "content": _VISION_SYSTEM},
            {"role": "user", "content": content},
        ],
        max_completion_tokens=2048,
        temperature=0.3,
    )

    raw = response.choices[0].message.content or ""

    # Extract identity block
    identity_features = raw
    if "---IDENTITY PROFILE BEGIN---" in raw and "---IDENTITY PROFILE END---" in raw:
        start = raw.find("---IDENTITY PROFILE BEGIN---")
        end = raw.find("---IDENTITY PROFILE END---") + len("---IDENTITY PROFILE END---")
        identity_features = raw[start:end]

    # Extract clothing analysis block
    clothing_analysis = None
    if "---CLOTHING ANALYSIS BEGIN---" in raw and "---CLOTHING ANALYSIS END---" in raw:
        start = raw.find("---CLOTHING ANALYSIS BEGIN---")
        end = raw.find("---CLOTHING ANALYSIS END---") + len("---CLOTHING ANALYSIS END---")
        clothing_analysis = raw[start:end]

    return {
        "identity_features": identity_features,
        "clothing_analysis": clothing_analysis,
        "has_user_photo": has_user_photo,
        "has_reference": has_reference,
    }
