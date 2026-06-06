"""DALL-E 3 image generation with prompt assembly and thumbnail compression."""
import asyncio
import uuid
from pathlib import Path

from PIL import Image
from openai import AsyncOpenAI

import config

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=config.OPENAI_API_KEY)
    return _client


SYSTEM_PROMPT = """你是一位专业的服装搭配设计师。根据用户提供的身体数据、风格偏好、场景需求和文字描述，设计一套完整的服装搭配效果图。

要求：
- 服装款式清晰可见，细节丰富
- 符合用户的身材数据
- 色彩搭配和谐
- 适合用户指定的场景
- 图片风格为时尚穿搭展示"""


def build_prompt(
    height: float,
    weight: float,
    bust: float | None,
    waist: float | None,
    hip: float | None,
    text: str | None,
    style_tags: list[str] | None,
    scene_tags: list[str] | None,
    has_reference: bool,
) -> str:
    """Assemble the full DALL-E prompt from user data and preferences."""

    parts = []

    # Body info
    body = f"用户身材：身高{height}cm，体重{weight}kg"
    if bust:
        body += f"，胸围{bust}cm"
    if waist:
        body += f"，腰围{waist}cm"
    if hip:
        body += f"，臀围{hip}cm"
    parts.append(body + "。")

    # Style tags
    if style_tags:
        parts.append(f"风格偏好：{'、'.join(style_tags)}。")

    # Scene tags
    if scene_tags:
        parts.append(f"穿着场景：{'、'.join(scene_tags)}。")

    # User text
    if text:
        parts.append(f"用户描述：{text}。")

    # Reference image note
    if has_reference:
        parts.append("用户提供了参考图片，请参考其中的服装风格和搭配方式。")

    parts.append("请生成一套完整的服装搭配效果图。")

    return SYSTEM_PROMPT + "\n\n" + " ".join(parts)


def _compress_image_sync(
    input_path: str,
    max_width: int = 600,
    quality: int = 60,
) -> str:
    """Synchronous PIL resize+compress. Called via asyncio.to_thread."""
    thumb_name = f"{uuid.uuid4()}_thumb.jpg"
    thumb_path = config.UPLOAD_DIR / thumb_name

    img = Image.open(input_path)
    img = img.convert("RGB")

    if img.width > max_width:
        ratio = max_width / img.width
        new_height = int(img.height * ratio)
        img = img.resize((max_width, new_height), Image.LANCZOS)

    img.save(thumb_path, "JPEG", quality=quality, optimize=True)
    return thumb_name


async def compress_image(
    input_path: str,
    max_width: int = 600,
    quality: int = 60,
) -> str:
    """Async wrapper: calls sync PIL code in a thread to avoid blocking the event loop."""
    return await asyncio.to_thread(_compress_image_sync, input_path, max_width, quality)


async def generate_image(
    prompt: str,
    size: str = "1024x1024",
) -> dict:
    """Call DALL-E 3 to generate an image. Returns {image_url, revised_prompt}."""

    response = await _get_client().images.generate(
        model="dall-e-3",
        prompt=prompt,
        size=size,
        quality="standard",
        n=1,
    )

    return {
        "image_url": response.data[0].url,
        "revised_prompt": response.data[0].revised_prompt or prompt,
    }
